# Optional camera motion eye

Disabled unless a separate user service is enabled. Camera addresses and settings
belong in `~/.config/nexus/camera.json`, outside the public checkout. Install Pillow
(`python3-pil` on the Pi) for the worker. No camera firmware changes are required.

Example private configuration (replace the hostname locally):

```json
{"capture_url":"http://camera.local/capture", "observe":true,
 "interval":2, "roi":[0,0,1,1], "pixel_threshold":18, "fraction":0.08}
```

ROI is normalized left, top, right, bottom. Crop out windows, moving vegetation
and display reflections. The existing camera capture size is used, with JPEGs
limited to 512 KiB / 2 megapixels and reduced in memory to 32×24 grayscale samples.
No frames or credentials are logged. No stream, face recognition, occupancy claim,
LED, sounds, page switching or alert escalation. Sampling increases camera/network
workload and may reduce battery runtime. Record its start separately from a
status-only baseline. Reachability cannot distinguish power loss from Wi-Fi loss.

The worker uses three consecutive differences above a changed-area threshold,
subtracts median brightness shift, and rejects broad exposure changes. False
positives from shadows/camera movement remain possible. Quiet subjects and slow
motion may be missed. Activity holds for 12 seconds, fades over 20 seconds, and
uses at most one two-second flourish per 30 seconds. The eye is cyan, never a
flashing emergency indicator. A slash means camera data is unavailable; existing
Pi offline handling remains independent and takes priority.

Start with `observe:true` for a day. This writes scores and candidate/confirmed
states without adding an eye to either screen. Inspect
`~/.local/state/nexus-camera/motion.json` and daily `motion-YYYY-MM-DD.jsonl` logs.
Logs are sampled every ten seconds plus availability changes and retained for
seven days. Existing `checks.jsonl` availability logs remain independent.

After installing modules and the user unit:

```sh
systemctl --user daemon-reload
systemctl --user enable --now nexus-camera-motion.service
```

The worker reloads configuration each cycle. After tuning, change `observe` to
`false` to enable the small header eye on both displays without restarting them.
The visual mode uses the same capture rate as observation mode. The worker does
not fetch from render threads. Readers treat results older than 15 seconds as
unavailable. HTTP redirects and system proxies are disabled; fetch exceptions are
logged by class only, never URLs or response bodies. Socket timeout is four
seconds with bounded reads; DNS resolution may exceed that timeout.

To return to the original battery workload:

```sh
systemctl --user disable --now nexus-camera-motion.service
rm -f ~/.local/state/nexus-camera/motion.json
```

The separate once-per-minute availability probe can continue. Neither private
configuration nor logs/images should be committed to the public repository.
