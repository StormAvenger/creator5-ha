"""Original explanations of selected vendor-published Creator 5 code meanings."""

SOURCE = "https://wiki.flashforge.com/en/creator-series/creator-5-series/error_code_creator_5"

ERRORS = {
    "E0162": (
        "Filament detection interrupted the print",
        "Check filament supply and the printer screen before resuming.",
    ),
    "E0163": (
        "Filament movement problem detected",
        "Inspect the filament path and follow the vendor's clog troubleshooting.",
    ),
    "E0166": (
        "The printer rejected the print file",
        "Check that the file was sliced correctly; re-slice if needed.",
    ),
    "E0169": (
        "Slice uses a different printer model",
        "Select the matching Creator 5 model in the slicer.",
    ),
    "E0077": (
        "Chamber heater reported a fault",
        "Use the vendor's chamber-heating checks before further printing.",
    ),
    "E0123": (
        "Build-plate heating reported a fault",
        "Use the vendor's bed-heating troubleshooting.",
    ),
}
for tool in range(1, 5):
    ERRORS[f"E{50 + tool:04}"] = (
        f"Tool {tool} could not be picked up",
        "Check the vendor's tool-pickup troubleshooting.",
    )
    ERRORS[f"E{62 + tool:04}"] = (
        f"Tool {tool} heating or file-validation issue",
        "Check the screen; the vendor lists heating faults "
        "and slice-annotation limits for this code.",
    )


def explanation(status):
    code = status.error_code
    if code in (None, "none") and status.state == "error":
        return "Printer reports an error", "Check its screen for details.", False
    if code == "none":
        return "No reported error", "", True
    if code is None:
        return None, None, False
    title, hint = (ERRORS if status.model is not None else {}).get(
        code,
        ("Unrecognized printer error", "Check the code on the printer and the vendor reference."),
    )
    return title, hint, status.model is not None and code in ERRORS
