"""
TensorRT Engine Loader for Clarity+ ML Services
================================================
Utilities for loading and running TensorRT optimized models.
Optimized for NVIDIA Jetson with FP16 precision support.
"""

import logging
import os
from typing import Optional, Dict, Tuple, List
import numpy as np

from config import settings, get_model_path

logger = logging.getLogger("clarity-ml.tensorrt")

# TensorRT availability flag
_TENSORRT_AVAILABLE = False

try:
    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit
    _TENSORRT_AVAILABLE = True
    logger.info("TensorRT runtime initialized successfully")
except ImportError as e:
    logger.warning(f"TensorRT not available: {e}. Using fallback CPU inference.")


class TensorRTEngine:
    """
    TensorRT inference engine wrapper optimized for FP16 on Jetson.
    
    Handles:
        - Engine loading from .engine files
        - CUDA memory management
        - Asynchronous inference with streams
        - FP16 precision (configurable)
    """
    
    def __init__(self, engine_path: str):
        """
        Initialize TensorRT engine from serialized .engine file.
        
        Args:
            engine_path: Path to the .engine TensorRT file
        """
        self.engine_path = engine_path
        self.engine = None
        self.context = None
        self.stream = None
        
        # I/O buffer management
        self.inputs: List[Dict] = []
        self.outputs: List[Dict] = []
        self.bindings: List[int] = []
        
        self._loaded = False
    
    def load(self) -> bool:
        """Load the TensorRT engine and allocate buffers."""
        if not _TENSORRT_AVAILABLE:
            logger.error("TensorRT not available on this system")
            return False
        
        if not os.path.exists(self.engine_path):
            logger.error(f"Engine file not found: {self.engine_path}")
            return False
        
        try:
            # Initialize TensorRT logger
            trt_logger = trt.Logger(trt.Logger.WARNING)
            
            # Load serialized engine
            logger.info(f"Loading TensorRT engine: {self.engine_path}")
            with open(self.engine_path, "rb") as f:
                runtime = trt.Runtime(trt_logger)
                self.engine = runtime.deserialize_cuda_engine(f.read())
            
            if self.engine is None:
                logger.error("Failed to deserialize engine")
                return False
            
            # Create execution context
            self.context = self.engine.create_execution_context()
            
            # Create CUDA stream for async inference
            self.stream = cuda.Stream()
            
            # Allocate I/O buffers
            self._allocate_buffers()
            
            self._loaded = True
            logger.info(f"Engine loaded successfully: {engine_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load engine: {e}")
            return False
    
    def _allocate_buffers(self):
        """Allocate CUDA device and host memory for I/O."""
        self.inputs = []
        self.outputs = []
        self.bindings = []
        
        for i in range(self.engine.num_bindings):
            name = self.engine.get_binding_name(i)
            dtype = trt.nptype(self.engine.get_binding_dtype(i))
            shape = self.engine.get_binding_shape(i)
            size = trt.volume(shape)
            
            # Allocate host and device memory
            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)
            
            self.bindings.append(int(device_mem))
            
            binding_info = {
                "name": name,
                "shape": shape,
                "dtype": dtype,
                "host": host_mem,
                "device": device_mem
            }
            
            if self.engine.binding_is_input(i):
                self.inputs.append(binding_info)
            else:
                self.outputs.append(binding_info)
        
        logger.info(f"Allocated {len(self.inputs)} inputs, {len(self.outputs)} outputs")
    
    def infer(self, input_data: np.ndarray) -> Optional[np.ndarray]:
        """
        Run inference on input data.
        
        Args:
            input_data: Preprocessed input tensor
        
        Returns:
            Output tensor from the model
        """
        if not self._loaded:
            logger.error("Engine not loaded")
            return None
        
        try:
            # Copy input to host buffer
            np.copyto(self.inputs[0]["host"], input_data.ravel())
            
            # Transfer to device
            cuda.memcpy_htod_async(
                self.inputs[0]["device"],
                self.inputs[0]["host"],
                self.stream
            )
            
            # Execute inference
            self.context.execute_async_v2(
                bindings=self.bindings,
                stream_handle=self.stream.handle
            )
            
            # Transfer outputs back to host
            for output in self.outputs:
                cuda.memcpy_dtoh_async(
                    output["host"],
                    output["device"],
                    self.stream
                )
            
            # Synchronize stream
            self.stream.synchronize()
            
            # Return output reshaped to proper dimensions
            return self.outputs[0]["host"].reshape(self.outputs[0]["shape"])
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return None
    
    def get_input_shape(self) -> Tuple:
        """Get the expected input shape."""
        if self.inputs:
            return tuple(self.inputs[0]["shape"])
        return ()
    
    def get_output_shape(self) -> Tuple:
        """Get the output shape."""
        if self.outputs:
            return tuple(self.outputs[0]["shape"])
        return ()
    
    def cleanup(self):
        """Free CUDA resources."""
        if self._loaded:
            for inp in self.inputs:
                inp["device"].free()
            for out in self.outputs:
                out["device"].free()
            self._loaded = False
            logger.info("Engine resources cleaned up")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()


def load_engine(model_name: str) -> Optional[TensorRTEngine]:
    """
    Load a TensorRT engine from the models directory.
    
    Args:
        model_name: Name of the .engine file (without extension)
    
    Returns:
        Loaded TensorRTEngine or None if loading fails
    """
    engine_path = get_model_path(f"{model_name}.engine")
    
    if not os.path.exists(engine_path):
        logger.warning(f"Engine file not found: {engine_path}")
        return None
    
    engine = TensorRTEngine(engine_path)
    if engine.load():
        return engine
    
    return None


def convert_onnx_to_tensorrt(
    onnx_path: str,
    output_path: str,
    fp16: bool = True,
    max_batch_size: int = 1,
    max_workspace_size: int = 1 << 30  # 1GB
) -> bool:
    """
    Convert an ONNX model to TensorRT engine with FP16 optimization.
    
    Args:
        onnx_path: Path to ONNX model file
        output_path: Path to save the .engine file
        fp16: Enable FP16 precision (default: True for Jetson optimization)
        max_batch_size: Maximum batch size for optimization
        max_workspace_size: GPU memory workspace in bytes
    
    Returns:
        True if conversion successful, False otherwise
    """
    if not _TENSORRT_AVAILABLE:
        logger.error("TensorRT not available for conversion")
        return False
    
    if not os.path.exists(onnx_path):
        logger.error(f"ONNX file not found: {onnx_path}")
        return False
    
    try:
        logger.info(f"Converting ONNX to TensorRT: {onnx_path}")
        logger.info(f"FP16 precision: {fp16}")
        
        trt_logger = trt.Logger(trt.Logger.WARNING)
        
        # Create builder and network
        builder = trt.Builder(trt_logger)
        network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
        network = builder.create_network(network_flags)
        
        # Parse ONNX model
        parser = trt.OnnxParser(network, trt_logger)
        with open(onnx_path, "rb") as f:
            if not parser.parse(f.read()):
                for i in range(parser.num_errors):
                    logger.error(f"ONNX parse error: {parser.get_error(i)}")
                return False
        
        # Configure builder
        config = builder.create_builder_config()
        config.max_workspace_size = max_workspace_size
        
        if fp16 and builder.platform_has_fast_fp16:
            config.set_flag(trt.BuilderFlag.FP16)
            logger.info("FP16 mode enabled (hardware supported)")
        elif fp16:
            logger.warning("FP16 requested but not supported by hardware")
        
        # Build engine
        logger.info("Building TensorRT engine (this may take several minutes)...")
        engine = builder.build_engine(network, config)
        
        if engine is None:
            logger.error("Failed to build TensorRT engine")
            return False
        
        # Serialize and save
        with open(output_path, "wb") as f:
            f.write(engine.serialize())
        
        logger.info(f"TensorRT engine saved: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"ONNX to TensorRT conversion failed: {e}")
        return False


def is_tensorrt_available() -> bool:
    """Check if TensorRT is available on this system."""
    return _TENSORRT_AVAILABLE
