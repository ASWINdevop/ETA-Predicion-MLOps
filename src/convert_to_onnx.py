import json
import os
import xgboost as xgb
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

def convert_models():
    print("🔄 Starting ONNX Conversion...")
    
    if not os.path.exists("model_manifest.json"):
        print("❌ Error: model_manifest.json not found.")
        return

    with open("model_manifest.json", "r") as f:
        manifest = json.load(f)

    # Define Input Shapes
    model_shapes = {
        "ETA_Cooking_Prediction": 4,
        "ETA_Allocation_Prediction": 3,
        "ETA_LastMile_Prediction": 4
    }

    new_manifest = {}

    for name, path in manifest.items():
        if name not in model_shapes:
            continue
            
        print(f"🔹 Converting {name}...")
        
        try:
      
            booster = xgb.Booster()
            booster.load_model(path)
            
            # 2. FIX: Rename features to f0, f1, f2... 
            # This prevents the "Unable to interpret feature name" error
            num_features = model_shapes[name]
            generic_names = [f"f{i}" for i in range(num_features)]
            booster.feature_names = generic_names
            
            initial_type = [('float_input', FloatTensorType([None, num_features]))]

            onnx_model = onnxmltools.convert_xgboost(booster, initial_types=initial_type)

            new_path = path.replace(".ubj", ".onnx")
            onnxmltools.utils.save_model(onnx_model, new_path)
            
            new_manifest[name] = new_path
            print(f"✅ Saved: {new_path}")
            
        except Exception as e:
            print(f"❌ Failed to convert {name}: {e}")

    # Save new manifest
    with open("onnx_manifest.json", "w") as f:
        json.dump(new_manifest, f, indent=4)
    
    print("📋 ONNX Manifest created: onnx_manifest.json")

if __name__ == "__main__":
    convert_models()