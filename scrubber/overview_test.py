from overview import generate_csv_overview

# List of your test CSV files shown in the workspace
csv_files = [
    "messy_data_one.csv",
    "messy_data_two.csv",
    "messy_data_three.csv"
]

print("=== RUNNING OVERVIEW TESTS ===\n")

for filename in csv_files:
    print(f"📁 Testing file: {filename}")
    print("-" * 50)
    
    try:
        # Read the CSV file as a string
        with open(filename, "r", encoding="utf-8") as f:
            csv_content = f.read()
            
        # Generate and print the overview
        overview_result = generate_csv_overview(csv_content)
        print(f"Output:\n{overview_result}\n")
        
    except FileNotFoundError:
        print(f"⚠️ Warning: {filename} not found in the current directory.\n")
    except Exception as e:
        print(f"❌ Error processing {filename}: {e}\n")

print("=== TEST COMPLETE ===")