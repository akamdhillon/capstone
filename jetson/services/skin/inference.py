"""
Inference and prediction aggregation for multi-angle acne assessment.
"""

import torch
import numpy as np
from torchvision import transforms
from PIL import Image
from collections import Counter
from pathlib import Path
import json
from datetime import datetime

from model import AcneClassifier

class AcneInferenceSystem:
    """
    System for making predictions on multi-angle face images.
    """
    
    def __init__(self, model_path, device=None):
        """
        Initialize inference system.
        
        Args:
            model_path: Path to trained model checkpoint
            device: Device to run inference on (None for auto-detect)
        """
        # Setup device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = device
        
        print(f"Using device: {self.device}")
        
        # Load model
        print(f"Loading model from: {model_path}")
        self.model = self._load_model(model_path)
        self.model.eval()
        
        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # Class names
        self.class_names = ['Clear', 'Mild', 'Moderate', 'Severe', 'Other']
        
        # Angle to facial region mapping
        self.angle_to_regions = {
            'Front': ['Full Face', 'Forehead', 'Nose', 'Chin'],
            'Left': ['Left Cheek', 'Left Temple'],
            'Right': ['Right Cheek', 'Right Temple'],
            'Up': ['Chin', 'Jawline', 'Neck'],
            'Down': ['Forehead', 'Upper Face']
        }
    
    def _load_model(self, model_path):
        """
        Load model from checkpoint.
        
        Args:
            model_path: Path to checkpoint file
            
        Returns:
            Loaded model
        """
        checkpoint = torch.load(model_path, map_location=self.device)
        
        model = AcneClassifier(num_classes=5, pretrained=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        model = model.to(self.device)
        
        print(f"Model loaded successfully!")
        print(f"  Validation accuracy: {checkpoint.get('val_acc', 'N/A')}")
        print(f"  Validation loss: {checkpoint.get('val_loss', 'N/A')}")
        
        return model
    
    def preprocess_image(self, image):
        """
        Preprocess image for model input.
        
        Args:
            image: PIL Image or numpy array
            
        Returns:
            Preprocessed tensor
        """
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Apply transforms
        tensor = self.transform(image)
        
        return tensor
    
    def predict_single(self, image):
        """
        Make prediction on a single image.
        
        Args:
            image: PIL Image or numpy array
            
        Returns:
            Dictionary with prediction results
        """
        # Preprocess
        tensor = self.preprocess_image(image).unsqueeze(0).to(self.device)
        
        # Predict
        with torch.no_grad():
            severity, classification = self.model(tensor)
            
            # Get probabilities
            probabilities = torch.softmax(classification, dim=1)
            predicted_class = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0, predicted_class].item()
        
        return {
            'class_idx': predicted_class,
            'class_name': self.class_names[predicted_class],
            'severity_score': severity.item(),
            'confidence': confidence,
            'probabilities': probabilities[0].cpu().numpy()
        }
    
    def predict_multi_angle(self, images, angle_names=None):
        """
        Make predictions on multiple angle images and aggregate results.
        
        Args:
            images: List of images (PIL Images or numpy arrays)
            angle_names: List of angle names (optional)
            
        Returns:
            Aggregated prediction results
        """
        if angle_names is None:
            angle_names = [f"Angle_{i+1}" for i in range(len(images))]
        
        # Make predictions for each angle
        individual_predictions = []
        
        print("\nAnalyzing individual angles...")
        for i, (image, angle_name) in enumerate(zip(images, angle_names)):
            pred = self.predict_single(image)
            pred['angle'] = angle_name
            individual_predictions.append(pred)
            
            print(f"  {angle_name:10s}: {pred['class_name']:10s} "
                  f"(confidence: {pred['confidence']*100:.1f}%, "
                  f"severity: {pred['severity_score']:.3f})")
        
        # Aggregate predictions
        aggregated = self._aggregate_predictions(individual_predictions)
        
        return {
            'individual': individual_predictions,
            'aggregated': aggregated
        }
    
    def _aggregate_predictions(self, predictions):
        """
        Aggregate multiple predictions into final assessment.
        
        Args:
            predictions: List of individual prediction dictionaries
            
        Returns:
            Aggregated results dictionary
        """
        # Extract predictions
        class_predictions = [p['class_idx'] for p in predictions]
        severity_scores = [p['severity_score'] for p in predictions]
        confidences = [p['confidence'] for p in predictions]
        
        # Majority voting for classification
        class_counts = Counter(class_predictions)
        majority_class = class_counts.most_common(1)[0][0]
        
        # Calculate agreement (consistency)
        agreement = class_counts[majority_class] / len(predictions)
        
        # Average severity score
        avg_severity = np.mean(severity_scores)
        std_severity = np.std(severity_scores)
        
        # Average confidence
        avg_confidence = np.mean(confidences)
        
        # Calculate overall confidence based on agreement and individual confidences
        overall_confidence = agreement * avg_confidence
        
        # Convert severity to 0-10 scale
        severity_score_10 = avg_severity * 10
        
        # Regional analysis
        regional_analysis = self._analyze_regions(predictions)
        
        # Recommendation based on severity
        recommendation = self._get_recommendation(majority_class, severity_score_10)
        
        return {
            'classification': self.class_names[majority_class],
            'class_idx': majority_class,
            'severity_score': severity_score_10,
            'severity_raw': avg_severity,
            'severity_std': std_severity,
            'confidence': overall_confidence,
            'agreement': agreement,
            'individual_confidence': avg_confidence,
            'num_images': len(predictions),
            'regional_analysis': regional_analysis,
            'recommendation': recommendation
        }
    
    def _analyze_regions(self, predictions):
        """
        Analyze acne by facial region based on angle predictions.
        
        Args:
            predictions: List of individual prediction dictionaries
            
        Returns:
            Regional analysis dictionary
        """
        region_scores = {}
        region_counts = {}
        
        for pred in predictions:
            angle = pred['angle']
            severity = pred['severity_score']
            
            # Get regions for this angle
            regions = self.angle_to_regions.get(angle, [angle])
            
            for region in regions:
                if region not in region_scores:
                    region_scores[region] = []
                    region_counts[region] = 0
                
                region_scores[region].append(severity)
                region_counts[region] += 1
        
        # Calculate average scores per region
        regional_analysis = {}
        for region, scores in region_scores.items():
            avg_score = np.mean(scores) * 10  # Scale to 0-10
            
            # Categorize severity
            if avg_score < 2.0:
                category = 'Clear'
            elif avg_score < 4.0:
                category = 'Low'
            elif avg_score < 6.0:
                category = 'Medium'
            elif avg_score < 8.0:
                category = 'High'
            else:
                category = 'Very High'
            
            regional_analysis[region] = {
                'score': avg_score,
                'category': category,
                'confidence': len(scores) / len(predictions)  # Based on coverage
            }
        
        return regional_analysis
    
    def _get_recommendation(self, class_idx, severity_score):
        """
        Generate recommendation based on classification and severity.
        
        Args:
            class_idx: Predicted class index
            severity_score: Severity score (0-10)
            
        Returns:
            Recommendation text
        """
        class_name = self.class_names[class_idx]
        
        if class_name == 'Clear' or severity_score < 2.0:
            return "Your skin appears clear. Maintain good skincare routine."
        
        elif class_name == 'Mild' or severity_score < 4.0:
            return "Mild acne detected. Over-the-counter treatments may be effective. Consider consulting a dermatologist if it persists."
        
        elif class_name == 'Moderate' or severity_score < 7.0:
            return "Moderate acne detected. We recommend consulting a dermatologist for personalized treatment options."
        
        elif class_name == 'Severe' or severity_score >= 7.0:
            return "Severe acne detected. Please consult a dermatologist for professional treatment. Early intervention can help prevent scarring."
        
        elif class_name == 'Other':
            return "Detected skin condition that may not be acne. Please consult a dermatologist for proper diagnosis."
        
        else:
            return "Please consult a healthcare professional for personalized advice."
    
    def save_results(self, results, output_path):
        """
        Save prediction results to JSON file.
        
        Args:
            results: Prediction results dictionary
            output_path: Path to save JSON file
        """
        # Convert numpy arrays to lists for JSON serialization
        results_serializable = self._make_serializable(results)
        
        # Add timestamp
        results_serializable['timestamp'] = datetime.now().isoformat()
        
        # Save to file
        with open(output_path, 'w') as f:
            json.dump(results_serializable, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")
    
    def _make_serializable(self, obj):
        """Recursively convert numpy types to Python types for JSON."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        else:
            return obj

def load_images_from_directory(directory, extensions=['.jpg', '.jpeg', '.png']):
    """
    Load all images from a directory.
    
    Args:
        directory: Path to directory
        extensions: Valid image extensions
        
    Returns:
        List of PIL Images and their filenames
    """
    dir_path = Path(directory)
    images = []
    filenames = []
    
    for ext in extensions:
        for img_path in sorted(dir_path.glob(f'*{ext}')):
            try:
                img = Image.open(img_path).convert('RGB')
                images.append(img)
                filenames.append(img_path.stem)
            except Exception as e:
                print(f"Error loading {img_path}: {e}")
    
    return images, filenames

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python inference.py <model_path> <image_directory>")
        print("\nExample:")
        print("  python inference.py checkpoints/best_model.pth captures/")
        sys.exit(1)
    
    model_path = sys.argv[1]
    image_dir = sys.argv[2]
    
    # Initialize inference system
    print("="*60)
    print("ACNE ASSESSMENT INFERENCE")
    print("="*60)
    
    inference_system = AcneInferenceSystem(model_path)
    
    # Load images
    print(f"\nLoading images from: {image_dir}")
    images, angle_names = load_images_from_directory(image_dir)
    
    if not images:
        print("No images found!")
        sys.exit(1)
    
    print(f"Loaded {len(images)} images: {', '.join(angle_names)}")
    
    # Make predictions
    results = inference_system.predict_multi_angle(images, angle_names)
    
    # Print results (detailed output will be in display_results.py)
    print("\n" + "="*60)
    print("ASSESSMENT COMPLETE")
    print("="*60)
    
    agg = results['aggregated']
    print(f"\nClassification: {agg['classification']}")
    print(f"Severity Score: {agg['severity_score']:.1f}/10")
    print(f"Confidence: {agg['confidence']*100:.1f}%")
    print(f"\nRecommendation: {agg['recommendation']}")
    
    # Save results
    output_path = Path(image_dir) / 'assessment_results.json'
    inference_system.save_results(results, output_path)
