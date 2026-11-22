# Source me: `source tools/review/headless.sh` exports DISPLAY and XAUTHORITY of a headless mutter (wayland display
# `kn-dump`), so the dump window (AUI: X11 + GLX through its Xwayland) never pops up on the author's desktop.
# A running `kn-dump` mutter is reused, otherwise one is started (it stays for the next dumps). The virtual monitor is tall:
# the dump window is 1000×1560 and a compositor clamps a window to its monitor (kn::DUMP_PAGE_SIZE, PageDumpTest).
# Fails (returns 1) if mutter is not there or its Xwayland does not come up; the caller decides whether to go visible.
kn_headless() {
  local name=kn-dump pid xw display auth i
  pid=$(pgrep -f "mutter --headless --wayland-display $name( |$)" | head -1)
  if [ -z "$pid" ]; then
    command -v mutter >/dev/null || { echo "headless.sh: no mutter" >&2; return 1; }
    setsid env -u DISPLAY -u WAYLAND_DISPLAY mutter --headless --wayland-display "$name" --virtual-monitor 1200x1800 \
      >"${XDG_RUNTIME_DIR:-/tmp}/kn-dump-mutter.log" 2>&1 < /dev/null &
    disown 2>/dev/null || true
    for i in $(seq 50); do
      pid=$(pgrep -f "mutter --headless --wayland-display $name( |$)" | head -1)
      [ -n "$pid" ] && break; sleep 0.1
    done
  fi
  [ -n "$pid" ] || { echo "headless.sh: mutter did not start" >&2; return 1; }
  # its Xwayland is a child of the mutter: `Xwayland :N ... -auth <file>`
  for i in $(seq 100); do
    xw=$(pgrep -a -P "$pid" Xwayland | head -1)
    [ -n "$xw" ] && break; sleep 0.1
  done
  [ -n "$xw" ] || { echo "headless.sh: the Xwayland of mutter $pid did not come up" >&2; return 1; }
  display=$(sed -E 's/.*Xwayland (:[0-9]+).*/\1/' <<<"$xw")
  auth=$(sed -E 's/.* -auth ([^ ]+).*/\1/' <<<"$xw")
  export DISPLAY=$display XAUTHORITY=$auth
  unset WAYLAND_DISPLAY
}
kn_headless
