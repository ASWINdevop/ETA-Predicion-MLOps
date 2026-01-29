import json
import os
import glob

# Mapping Experiment ID -> Model Name
# Based on the order we created them: 
# Exp 1 = Cooking, Exp 2 = Allocation, Exp 3 = Delivery
EXP_MAP = {
    "1": "ETA_Cooking_Prediction",
    "2": "ETA_Allocation_Prediction",
    "3": "ETA_LastMile_Prediction"
}

OUTPUT_FILE = "model_manifest.json"

def create_manifest():
    print("🔍 Scanning Disk for Models (Brute Force)...")
    manifest = {}
    
    # We assume the mlruns folder is in the current directory
    base_dir = "mlruns"
    
    for exp_id, model_name in EXP_MAP.items():
        search_path = os.path.join(base_dir, exp_id)
        

        found_files = []
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if file in ["model.ubj", "model.xgb", "model.json"]:
                    full_path = os.path.join(root, file)
                    found_files.append(full_path)
        
        if not found_files:
            print(f"❌ No model files found in {search_path}")
            continue
            
       
        latest_file = max(found_files, key=os.path.getmtime)
        
      
        relative_path = latest_file.replace("\\", "/")
        manifest[model_name] = relative_path
        
        print(f"✅ mapped '{model_name}' -> {relative_path}")


    with open(OUTPUT_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n📄 Manifest saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    create_manifest()