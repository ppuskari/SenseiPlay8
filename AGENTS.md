# Repository agent instructions

Scope: standalone SenseiPlay8 Apple IIe application. Build and test with Python 3. Keep P0 working and preserve source provenance in recovery/. Hardware interface is specific to ppuskari/a2fpga_core and must be checked against the exact RTL before claiming physical validation. Do not import or change Mockingboard FX, piano or SSI263 firmware. Prefer 6502-safe opcodes; do not assume TransWarp IIe, AUX RAM, 65816 or GS/OS. Tests are software-only unless explicitly run on a real Apple IIe.
