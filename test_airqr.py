import os
import airqr

def test_run_sender_non_existent_file(capsys):
    """
    Test that run_sender correctly handles a non-existent file path by printing
    an error message and returning, rather than attempting to proceed.
    """
    non_existent_file = "this_file_does_not_exist_12345.txt"

    # Ensure the file doesn't exist
    if os.path.exists(non_existent_file):
        os.remove(non_existent_file)

    # Call run_sender with the non-existent file
    airqr.run_sender(non_existent_file, camera_index=0)

    # Capture the output
    captured = capsys.readouterr()

    # Verify the error message was printed
    expected_error = f"Error: File {non_existent_file} not found."
    assert expected_error in captured.out
