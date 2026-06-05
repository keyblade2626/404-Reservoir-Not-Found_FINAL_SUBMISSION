from app.grdecl_properties import inspect_grdecl_files

result = inspect_grdecl_files()

for name, payload in result.items():
    print("")
    print("=" * 80)
    print(name)
    print("=" * 80)
    for key, value in payload.items():
        print(f"{key}: {value}")
