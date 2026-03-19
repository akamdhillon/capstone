"""
Acne Classification Model using EfficientNet-B0 backbone.
Multi-task learning with classification and severity regression heads.
"""

import torch
import torch.nn as nn
import timm

class AcneClassifier(nn.Module):
    """
    EfficientNet-B0 based classifier for acne severity assessment.
    
    Outputs:
        - classification: 5-class prediction (clear, mild, moderate, severe, other)
        - severity: Continuous severity score [0-1]
    """
    
    def __init__(self, num_classes=5, pretrained=True, dropout=0.3):
        """
        Initialize the acne classifier.
        
        Args:
            num_classes: Number of classification classes (default: 5)
            pretrained: Use ImageNet pretrained weights (default: True)
            dropout: Dropout probability (default: 0.3)
        """
        super(AcneClassifier, self).__init__()
        
        # Load EfficientNet-B0 backbone without classifier
        self.backbone = timm.create_model(
            'efficientnet_b0',
            pretrained=pretrained,
            num_classes=0,  # Remove default classifier
            global_pool='avg'  # Global average pooling
        )
        
        # Get feature dimension
        self.num_features = self.backbone.num_features
        
        # Classification head (5-class: clear, mild, moderate, severe, other)
        self.classification_head = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(self.num_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout * 0.5),
            nn.Linear(256, num_classes)
        )
        
        # Severity regression head (continuous 0-1 score)
        self.severity_head = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(self.num_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout * 0.5),
            nn.Linear(256, 1),
            nn.Sigmoid()  # Output in [0, 1] range
        )
        
        # Class to severity score mapping (for training targets)
        # clear=0.0, mild=0.25, moderate=0.5, severe=0.85, other=None
        self.class_to_severity = {
            0: 0.0,    # clear
            1: 0.25,   # mild
            2: 0.5,    # moderate
            3: 0.85,   # severe
            4: None    # other (skip severity loss)
        }
    
    def forward(self, x):
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch_size, 3, 224, 224)
            
        Returns:
            severity: Severity scores of shape (batch_size, 1)
            classification: Class logits of shape (batch_size, num_classes)
        """
        # Extract features using backbone
        features = self.backbone(x)
        
        # Compute predictions from both heads
        severity = self.severity_head(features)
        classification = self.classification_head(features)
        
        return severity, classification
    
    def predict(self, x, device='cpu'):
        """
        Make predictions with post-processing.
        
        Args:
            x: Input tensor or PIL Image
            device: Device to run inference on
            
        Returns:
            dict with 'class', 'class_name', 'severity_score', 'probabilities'
        """
        self.eval()
        with torch.no_grad():
            # Handle single image
            if len(x.shape) == 3:
                x = x.unsqueeze(0)
            
            x = x.to(device)
            
            # Forward pass
            severity, classification = self.forward(x)
            
            # Get predictions
            probabilities = torch.softmax(classification, dim=1)
            predicted_class = torch.argmax(probabilities, dim=1)
            
            # Class names
            class_names = ['Clear', 'Mild', 'Moderate', 'Severe', 'Other']
            
            # Prepare results
            results = []
            for i in range(x.size(0)):
                class_idx = predicted_class[i].item()
                results.append({
                    'class': class_idx,
                    'class_name': class_names[class_idx],
                    'severity_score': severity[i].item(),
                    'probabilities': probabilities[i].cpu().numpy(),
                    'confidence': probabilities[i, class_idx].item()
                })
            
            return results[0] if len(results) == 1 else results

def create_model(num_classes=5, pretrained=True, device='cpu'):
    """
    Factory function to create and initialize model.
    
    Args:
        num_classes: Number of classification classes
        pretrained: Use ImageNet pretrained weights
        device: Device to load model on
        
    Returns:
        Initialized model
    """
    model = AcneClassifier(num_classes=num_classes, pretrained=pretrained)
    model = model.to(device)
    return model

def get_severity_target(class_labels, class_to_severity_map):
    """
    Convert class labels to severity regression targets.
    
    Args:
        class_labels: Tensor of class indices
        class_to_severity_map: Dict mapping class indices to severity scores
        
    Returns:
        severity_targets: Tensor of severity scores
        valid_mask: Boolean mask for valid severity targets
    """
    batch_size = class_labels.size(0)
    severity_targets = torch.zeros(batch_size, dtype=torch.float32)
    valid_mask = torch.ones(batch_size, dtype=torch.bool)
    
    for i, class_idx in enumerate(class_labels):
        severity_score = class_to_severity_map.get(class_idx.item())
        if severity_score is not None:
            severity_targets[i] = severity_score
        else:
            valid_mask[i] = False  # Skip 'other' class in severity loss
    
    return severity_targets, valid_mask

if __name__ == "__main__":
    # Test model
    print("Testing AcneClassifier...")
    
    # Create model
    model = create_model(num_classes=5, pretrained=False)
    
    # Test forward pass
    batch_size = 4
    dummy_input = torch.randn(batch_size, 3, 224, 224)
    
    severity, classification = model(dummy_input)
    
    print(f"\nModel architecture:")
    print(f"  Backbone: EfficientNet-B0")
    print(f"  Feature dimension: {model.num_features}")
    print(f"  Number of classes: 5")
    
    print(f"\nOutput shapes:")
    print(f"  Severity: {severity.shape} (expected: [{batch_size}, 1])")
    print(f"  Classification: {classification.shape} (expected: [{batch_size}, 5])")
    
    print(f"\nSeverity range: [{severity.min().item():.3f}, {severity.max().item():.3f}]")
    
    # Test prediction
    result = model.predict(dummy_input[0])
    print(f"\nSample prediction:")
    print(f"  Class: {result['class_name']}")
    print(f"  Severity: {result['severity_score']:.3f}")
    print(f"  Confidence: {result['confidence']:.3f}")
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"\nModel parameters:")
    print(f"  Total: {total_params:,}")
    print(f"  Trainable: {trainable_params:,}")
    
    print("\n✓ Model test complete!")
