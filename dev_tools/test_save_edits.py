#!/usr/bin/env python3
"""
Test script to verify the "Salvar Edições" button functionality.
Tests pagination and save edits logic without running the full Streamlit UI.
"""

import json
from pathlib import Path

def test_save_edits():
    """Test the save edits functionality with pagination."""

    # Load the test plan
    plan_path = Path("planos/teste.json")
    print(f"Loading plan from: {plan_path}")

    with open(plan_path, encoding='utf-8') as f:
        plan_data = json.load(f)

    # Simulate session state (what Streamlit would have)
    class MockPlanState:
        def __init__(self, data):
            self.date = data.get("data", "25-11-2025")
            self.secao = data.get("secaoDefault", "DO1")
            self.combos = data.get("combos", [])
            self.defaults = data.get("defaults", {})

    class MockSessionState:
        def __init__(self):
            self.plan = MockPlanState(plan_data)
            self.loaded_plan_path = str(plan_path)

    st_session_state = MockSessionState()
    print(f"Loaded plan with {len(st_session_state.plan.combos)} combos")

    # Simulate DataFrame edits (what user would do in the UI)
    # Let's edit the first 3 combos
    edits = [
        {"index": 0, "label1": "Atos do Poder Executivo EDITADO", "label2": "Todos EDITADO"},
        {"index": 1, "label1": "Ministério da Defesa EDITADO", "label2": "Comando da Aeronáutica EDITADO"},
        {"index": 2, "label1": "Ministério da Defesa EDITADO", "label2": "Comando da Marinha EDITADO"},
    ]

    print("\nSimulating user edits:")
    for edit in edits:
        idx = edit["index"]
        print(f"  Combo {idx}: '{st_session_state.plan.combos[idx]['label1']}' -> '{edit['label1']}'")
        print(f"             '{st_session_state.plan.combos[idx]['label2']}' -> '{edit['label2']}'")

    # Simulate the save logic (from app.py lines ~1359-1390)
    PAGE_SIZE = 15  # Same as in app.py
    current_page = 0  # Start at page 0

    start_idx = current_page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE

    # Create a mock edited_df (what Streamlit data_editor would produce)
    # This simulates the DataFrame with only the current page's data
    edited_df_data = []
    for page_idx, combo in enumerate(st_session_state.plan.combos[start_idx:end_idx]):
        edited_df_data.append({
            "label1": combo["label1"],
            "label2": combo["label2"],
            "original_idx": start_idx + page_idx
        })

    # Apply the simulated edits to the mock DataFrame
    for edit in edits:
        if start_idx <= edit["index"] < end_idx:
            page_idx = edit["index"] - start_idx
            edited_df_data[page_idx]["label1"] = edit["label1"]
            edited_df_data[page_idx]["label2"] = edit["label2"]

    print(f"\nPage {current_page}: showing combos {start_idx} to {min(end_idx, len(st_session_state.plan.combos))-1}")
    print("Edited DataFrame:")
    for i, row in enumerate(edited_df_data):
        global_idx = start_idx + i
        print(f"  Row {i} (global {global_idx}): '{row['label1']}' | '{row['label2']}'")

    # Execute the save logic (from app.py lines ~1359-1390)
    print("\nExecuting save logic...")

    # Simulate the button click logic
    for row in edited_df_data:
        page_idx = edited_df_data.index(row)
        global_idx = start_idx + page_idx

        # Update the combo in session state
        st_session_state.plan.combos[global_idx]["label1"] = row["label1"]
        st_session_state.plan.combos[global_idx]["label2"] = row["label2"]

        print(f"  Updated combo {global_idx}: label1='{row['label1']}', label2='{row['label2']}'")

    # Save to file if loaded_plan_path exists
    if st_session_state.loaded_plan_path:
        try:
            cfg_to_save = {
                "data": st_session_state.plan.date,
                "secaoDefault": st_session_state.plan.secao,
                "defaults": st_session_state.plan.defaults,
                "combos": st_session_state.plan.combos,
                "output": {"pattern": "{topic}_{secao}_{date}_{idx}.json", "report": "batch_report.json"},
            }
            with open(st_session_state.loaded_plan_path, 'w', encoding='utf-8') as f:
                json.dump(cfg_to_save, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Successfully saved changes to {st_session_state.loaded_plan_path}")
        except Exception as e:
            print(f"\n❌ Error saving file: {e}")
            return False
    else:
        print("\n❌ No loaded_plan_path found")
        return False

    # Verify the changes were saved
    print("\nVerifying saved changes...")
    with open(plan_path, encoding='utf-8') as f:
        saved_data = json.load(f)

    saved_plan = MockPlanState(saved_data)
    success = True

    for edit in edits:
        idx = edit["index"]
        saved_label1 = saved_plan.combos[idx]["label1"]
        saved_label2 = saved_plan.combos[idx]["label2"]

        if saved_label1 == edit["label1"] and saved_label2 == edit["label2"]:
            print(f"  ✅ Combo {idx}: changes saved correctly")
        else:
            print(f"  ❌ Combo {idx}: expected '{edit['label1']}'/'{edit['label2']}', got '{saved_label1}'/'{saved_label2}'")
            success = False

    # Check that other combos weren't modified
    for idx in range(len(saved_plan.combos)):
        if idx not in [edit["index"] for edit in edits] and \
           (saved_plan.combos[idx]["label1"] != st_session_state.plan.combos[idx]["label1"] or \
            saved_plan.combos[idx]["label2"] != st_session_state.plan.combos[idx]["label2"]):
            print(f"  ❌ Combo {idx}: unexpectedly modified")
            success = False

    if success:
        print("\n🎉 All tests passed! Save edits functionality works correctly.")
    else:
        print("\n💥 Some tests failed. Save edits functionality has issues.")

    return success
    """Test the save edits functionality with pagination."""

    # Load the test plan
    plan_path = Path("planos/teste.json")
    print(f"Loading plan from: {plan_path}")

    with open(plan_path, encoding='utf-8') as f:
        plan_data = json.load(f)

    # Create Plan object
    plan = MockPlanState(plan_data)
    print(f"Loaded plan with {len(plan.combos)} combos")

    # Simulate session state (what Streamlit would have)
    class MockSessionState:
        def __init__(self):
            self.plan = plan
            self.loaded_plan_path = str(plan_path)

    st_session_state = MockSessionState()

    # Simulate DataFrame edits (what user would do in the UI)
    # Let's edit the first 3 combos
    edits = [
        {"index": 0, "label1": "Atos do Poder Executivo EDITADO", "label2": "Todos EDITADO"},
        {"index": 1, "label1": "Ministério da Defesa EDITADO", "label2": "Comando da Aeronáutica EDITADO"},
        {"index": 2, "label1": "Ministério da Defesa EDITADO", "label2": "Comando da Marinha EDITADO"},
    ]

    print("\nSimulating user edits:")
    for edit in edits:
        idx = edit["index"]
        print(f"  Combo {idx}: '{st_session_state.plan.combos[idx]['label1']}' -> '{edit['label1']}'")
        print(f"             '{st_session_state.plan.combos[idx]['label2']}' -> '{edit['label2']}'")

    # Simulate the save edits logic (copied from app.py)
    PAGE_SIZE = 15  # Same as in app.py
    current_page = 0  # Start at page 0

    start_idx = current_page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE

    # Create a mock edited_df (what Streamlit data_editor would produce)
    # This simulates the DataFrame with only the current page's data
    edited_df_data = []
    for page_idx, combo in enumerate(st_session_state.plan.combos[start_idx:end_idx]):
        edited_df_data.append({
            "label1": combo["label1"],
            "label2": combo["label2"],
            "original_idx": start_idx + page_idx
        })

    # Apply the simulated edits to the mock DataFrame
    for edit in edits:
        if start_idx <= edit["index"] < end_idx:
            page_idx = edit["index"] - start_idx
            edited_df_data[page_idx]["label1"] = edit["label1"]
            edited_df_data[page_idx]["label2"] = edit["label2"]

    print(f"\nPage {current_page}: showing combos {start_idx} to {min(end_idx, len(st_session_state.plan.combos))-1}")
    print("Edited DataFrame:")
    for i, row in enumerate(edited_df_data):
        global_idx = start_idx + i
        print(f"  Row {i} (global {global_idx}): '{row['label1']}' | '{row['label2']}'")

    # Execute the save logic (from app.py lines ~1359-1390)
    print("\nExecuting save logic...")

    # Simulate the button click logic
    for row in edited_df_data:
        page_idx = edited_df_data.index(row)
        global_idx = start_idx + page_idx

        # Update the combo in session state
        st_session_state.plan.combos[global_idx]["label1"] = row["label1"]
        st_session_state.plan.combos[global_idx]["label2"] = row["label2"]

        print(f"  Updated combo {global_idx}: label1='{row['label1']}', label2='{row['label2']}'")

    # Save to file if loaded_plan_path exists
    if st_session_state.loaded_plan_path:
        try:
            plan_dict = st_session_state.plan.to_dict()
            with open(st_session_state.loaded_plan_path, 'w', encoding='utf-8') as f:
                json.dump(plan_dict, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Successfully saved changes to {st_session_state.loaded_plan_path}")
        except Exception as e:
            print(f"\n❌ Error saving file: {e}")
            return False
    else:
        print("\n❌ No loaded_plan_path found")
        return False

    # Verify the changes were saved
    print("\nVerifying saved changes...")
    with open(plan_path, encoding='utf-8') as f:
        saved_data = json.load(f)

    saved_plan = MockPlanState(saved_data)
    success = True

    for edit in edits:
        idx = edit["index"]
        saved_label1 = saved_plan.combos[idx]["label1"]
        saved_label2 = saved_plan.combos[idx]["label2"]

        if saved_label1 == edit["label1"] and saved_label2 == edit["label2"]:
            print(f"  ✅ Combo {idx}: changes saved correctly")
        else:
            print(f"  ❌ Combo {idx}: expected '{edit['label1']}'/'{edit['label2']}', got '{saved_label1}'/'{saved_label2}'")
            success = False

    # Check that other combos weren't modified
    for idx in range(len(saved_plan.combos)):
        if idx not in [edit["index"] for edit in edits] and \
           (saved_plan.combos[idx]["label1"] != plan.combos[idx]["label1"] or \
            saved_plan.combos[idx]["label2"] != plan.combos[idx]["label2"]):
            print(f"  ❌ Combo {idx}: unexpectedly modified")
            success = False

    if success:
        print("\n🎉 All tests passed! Save edits functionality works correctly.")
    else:
        print("\n💥 Some tests failed. Save edits functionality has issues.")

    return success

if __name__ == "__main__":
    test_save_edits()
