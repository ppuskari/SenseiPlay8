# SenseiPlay8 P1B — real MOD flow support

Added offline ProTracker Bxx order jumps, Dxx pattern breaks, and E6x loops.
The hardware-proven P0 playback engine and P1A ProDOS wrapper are unchanged.
Fxx speed/tempo and basic note-volume handling remain supported.
Unsupported tick-level effects are intentionally rejected.

The user-provided `1_minute_dead_waltz.mod` was audited privately: 15 orders,
14 D00 row-23 breaks, one E60/E61 loop, one 5,878-byte sampled instrument.
After flattening: 424 played rows, 8,192 DOC sample bytes, 21,176-byte
ProDOS SYS, approximately 60.07 seconds. An accompanying 140KB image was
created for hardware testing. The MOD itself is not added to GitHub.

PowerShell 5.1 (run one command per paste):

```powershell
cd C:\AppleIIgsDev_02\SenseiPlay8
git pull --ff-only
py -3 tools/import-p0.py recovery/senseiplay_iie_p0_sources.patch
py -3 tools/p1b_flow_build.py C:\Music\1_minute_dead_waltz.mod --analyze
py -3 tools/p1b_flow_build.py C:\Music\1_minute_dead_waltz.mod --out dist\SENSEI8-WALTZ.SYSTEM
```

Replace the illustrative C:\Music filename with the file's actual location.
Tick-level arpeggio, slides, vibrato, portamento and volume automation are
the next compatibility features. Native NTP files remain unsupported.
