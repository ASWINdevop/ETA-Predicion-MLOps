import json
import os
import xgboost as xgb
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

def convert_models():
    print("🔄 Starting ONNX Conversion & Extraction...")
    
    # 1. Check for the Input Manifest (from train.py)
    if not os.path.exists("model_manifest.json"):
        print("❌ Error: model_manifest.json not found. Did you run train.py?")
        return

    with open("model_manifest.json", "r") as f:
        manifest = json.load(f)

    # 2. Configuration: Map Experiment Names to Clean Filenames
    # This keeps the files in the root folder so Docker can find them easily.
    model_config = {
        "ETA_Cooking_Prediction": {
            "features": 4, 
            "filename": "cooking.onnx"
        },
        "ETA_Allocation_Prediction": {
            "features": 3, 
            "filename": "allocation.onnx"
        },
        "ETA_LastMile_Prediction": {
            "features": 4, 
            "filename": "delivery.onnx"
        }
    }

    new_manifest = {}

    for name, path in manifest.items():
        if name not in model_config:
            print(f"⚠️ Skipping unknown model: {name}")
            continue
            
        print(f"🔹 Converting {name}...")
        
        try:
            # A. Load the XGBoost Model from the deep mlruns folder
            booster = xgb.Booster()
            booster.load_model(path)
            
            # B. Sanitize Feature Names (Fixes "Unable to interpret feature name" error)
            num_features = model_config[name]["features"]
            generic_names = [f"f{i}" for i in range(num_features)]
            booster.feature_names = generic_names
            
            # C. Convert to ONNX
            initial_type = [('float_input', FloatTensorType([None, num_features]))]
            onnx_model = onnxmltools.convert_xgboost(booster, initial_types=initial_type)

            # D. Save to ROOT FOLDER (Crucial for Docker!)
            target_filename = model_config[name]["filename"]
            onnxmltools.utils.save_model(onnx_model, target_filename)
            
            # E. Update Manifest to point to local file
            new_manifest[name] = target_filename
            print(f"✅ Saved clean model to: ./{target_filename}")
            
        except Exception as e:
            print(f"❌ Failed to convert {name}: {e}")

    # 3. Save the new 'Docker-Ready' Manifest
    with open("onnx_manifest.json", "w") as f:
        json.dump(new_manifest, f, indent=4)
    
    print("\n📋 Success! Files created in root directory:")
    print("   - cooking.onnx")
    print("   - allocation.onnx")
    print("   - delivery.onnx")
    print("   - onnx_manifest.json")

if __name__ == "__main__":
    convert_models()