# DirkuLator bridge tools

Python 3.11+; standard library only. The controller bridge must be compiled into
DirkuLator and a physical controller must be connected, powered on, and neutral.
Use the console's FTP host explicitly; no personal host or path is embedded.

```sh
python3 client.py status --host PS5_HOST
python3 client.py arm --host PS5_HOST
python3 client.py pulse --host PS5_HOST --ly 0 --milliseconds 500
python3 client.py stop --host PS5_HOST
python3 hold.py --host PS5_HOST --seconds 60 --ly 0          # continuous movement
python3 hold.py --host PS5_HOST --seconds 600 --random       # both sticks at random
python3 capture_archive.py --host PS5_HOST --stop-when-title-exits
python3 test_capture_archive.py
```

Commands and applied acknowledgments are retained under `dirkulator-evidence`.
`hold.py` keeps a stick held beyond the three-second pulse limit by chaining overlapping pulses (3000 ms
long, one every 2000 ms), so every pulse still expires on its own and the input ends within three seconds if
the program or the connection dies. It ends early when the bridge cancels, stops or changes session, when the
file `bridge-hold-stop.txt` appears, or on Ctrl+C, and it ends with a neutral input that keeps the bridge armed.
Both tools accept `--evidence-dir` to share another output directory. Native
commands expire within three seconds and physical input cancels remote control.
The archiver preserves every produced capture file, nested stages, hashes, and
associated logs. It does not enable a timed capture cadence. `client.py capture`
requests a capture explicitly. Private evidence is not part of the public repo.
