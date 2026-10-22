"""
Line-by-line port of "Pivot Points High Low & Missed Reversal Levels [LuxAlgo]"
(Pine v5, (c) LuxAlgo, CC BY-NC-SA 4.0). Non-commercial use only.

Bars are processed one by one, exactly like Pine does, including the
`var` state and the `x[1]` (previous bar) references.
"""
import math

NAN = float("nan")


def isnan(x):
    return x != x


def pmax(a, b):  # Pine math.max: na if either side is na
    return NAN if isnan(a) or isnan(b) else max(a, b)


def pmin(a, b):
    return NAN if isnan(a) or isnan(b) else min(a, b)


def pivots(highs, lows, length, ties="left_strict"):
    """ta.pivothigh(length,length) / ta.pivotlow(length,length).

    Value for bar c is the pivot found at bar c-length (known `length` bars later).
    ties="left_strict": must be strictly beyond the left bars, may equal the right bars.
    ties="both_equal" : may equal on both sides.
    """
    n = len(highs)
    ph, pl = [None] * n, [None] * n
    for c in range(2 * length, n):
        i = c - length
        lh, rh = max(highs[i - length:i]), max(highs[i + 1:c + 1])
        ll, rl = min(lows[i - length:i]), min(lows[i + 1:c + 1])
        if ties == "both_equal":
            if highs[i] >= lh and highs[i] >= rh:
                ph[c] = highs[i]
            if lows[i] <= ll and lows[i] <= rl:
                pl[c] = lows[i]
        else:
            if highs[i] > lh and highs[i] >= rh:
                ph[c] = highs[i]
            if lows[i] < ll and lows[i] <= rl:
                pl[c] = lows[i]
    return ph, pl


def luxalgo(highs, lows, length=50, ties="left_strict"):
    """Returns dict with:
       regular : [(confirm_idx, 'buy'|'sell', pivot_idx, price)]   (the ▲ / ▼ labels)
       ghosts  : [(bar_idx, 'high'|'low', price)]                  (historical 👻 labels)
       segs    : [(x1, y1, x2, y2, dashed)]                        (zig-zag lines)
       provisional : {x, y, kind, from:(px1,py1)} or None          (last-bar 👻, REPAINTS)
    """
    N = len(highs)
    ph, pl = pivots(highs, lows, length, ties)

    mx = mn = fmax = fmin = NAN
    mx_x1 = mn_x1 = fmax_x1 = fmin_x1 = 0
    os_ = 0
    py1, px1 = 0.0, 0
    started = False

    regular, ghosts, segs = [], [], []

    def ghost(x, y, kind):
        if not isnan(y):
            ghosts.append((x, kind, y))

    def seg(x1, y1, x2, y2, dashed):
        if started and not isnan(y1) and not isnan(y2):
            segs.append((x1, y1, x2, y2, dashed))

    for n in range(N):
        prev_os = os_
        pmx, pmn, pfmax, pfmin = mx, mn, fmax, fmin  # values at end of previous bar
        hl = highs[n - length] if n >= length else NAN
        ll = lows[n - length] if n >= length else NAN

        mx = pmax(hl, mx)
        mn = pmin(ll, mn)
        fmax = pmax(hl, fmax)
        fmin = pmin(ll, fmin)

        if mx > pmx:
            mx_x1 = n - length
            fmin = ll
        if mn < pmn:
            mn_x1 = n - length
            fmax = hl
        if fmin < pfmin:
            fmin_x1 = n - length
        if fmax > pfmax:
            fmax_x1 = n - length

        # ------------------------------ pivot high ---------------------------
        if ph[n] is not None:
            p = ph[n]
            if prev_os == 1:
                ghost(mn_x1, mn, "low")
                seg(px1, py1, mn_x1, mn, True)
                px1, py1 = mn_x1, mn
                started = started or not isnan(mn)
            elif p < mx:
                ghost(mx_x1, mx, "high")
                ghost(fmin_x1, fmin, "low")
                seg(px1, py1, mx_x1, mx, True)
                px1, py1 = mx_x1, mx
                seg(px1, py1, fmin_x1, fmin, True)
                px1, py1 = fmin_x1, fmin
            regular.append((n, "sell", n - length, p))
            seg(px1, py1, n - length, p, (p < mx) or prev_os == 1)
            py1, px1, os_, mx, mn = p, n - length, 1, p, p
            started = True

        # ------------------------------ pivot low ----------------------------
        if pl[n] is not None:
            p = pl[n]
            if prev_os == 0:
                ghost(mx_x1, mx, "high")
                seg(px1, py1, mx_x1, mx, True)
                px1, py1 = mx_x1, mx
                started = started or not isnan(mx)
            elif p > mn:
                ghost(fmax_x1, fmax, "high")
                ghost(mn_x1, mn, "low")
                seg(px1, py1, mn_x1, mn, True)
                px1, py1 = mn_x1, mn
                seg(px1, py1, fmax_x1, fmax, True)
                px1, py1 = fmax_x1, fmax
            regular.append((n, "buy", n - length, p))
            seg(px1, py1, n - length, p, (p > mn) or prev_os == 0)
            py1, px1, os_, mx, mn = p, n - length, 0, p, p
            started = True

    # ------------------- barstate.islast: provisional 👻 ---------------------
    prov = None
    if started and px1 + 1 <= N - 1:
        rng = range(N - 1, px1, -1)  # latest bar first, like Pine's loop (i = 0..)
        if os_ == 1:
            y = min(lows[i] for i in rng)
            x = next(i for i in rng if lows[i] == y)
            kind = "low"
        else:
            y = max(highs[i] for i in rng)
            x = next(i for i in rng if highs[i] == y)
            kind = "high"
        prov = {"x": x, "y": y, "kind": kind, "from": (px1, py1)}

    return {"regular": regular, "ghosts": ghosts, "segs": segs, "provisional": prov}


def find_signals(highs, lows, length=50, ties="left_strict"):
    """Trading signals = the regular ▲/▼ labels only (confirmed, never repaint)."""
    return luxalgo(highs, lows, length, ties)["regular"]
