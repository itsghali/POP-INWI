import numpy as np
import scipy.stats


def exterior_causes_ambient_spike(amb_vals, ext_vals, spearman_thresh=0.5, min_ext_change=0.8,
                                   diff_corr_thresh=0.3, dir_agree_thresh=0.6):
    """Return True if exterior temperature likely caused the ambient spike.

    Criteria:
    - Spearman correlation between amb and ext >= spearman_thresh
    - Absolute ext change in window >= min_ext_change
    - Either first-diff correlation >= diff_corr_thresh OR directional agreement >= dir_agree_thresh
    """
    amb = np.asarray(amb_vals, dtype=float)
    ext = np.asarray(ext_vals, dtype=float)
    # remove NaNs
    mask = (~np.isnan(amb)) & (~np.isnan(ext))
    amb = amb[mask]
    ext = ext[mask]

    if len(amb) < 5:
        return False

    Ext_corr, _ = scipy.stats.spearmanr(amb, ext)
    if Ext_corr is None:
        return False

    ext_delta = np.nanmax(ext) - np.nanmin(ext)

    diff_corr = None
    dir_agreement = 0.0
    if len(ext) >= 4:
        diff_ext = np.diff(ext)
        diff_amb = np.diff(amb)
        if len(diff_ext) >= 3 and np.nanstd(diff_ext) > 0 and np.nanstd(diff_amb) > 0:
            diff_corr, _ = scipy.stats.spearmanr(diff_amb, diff_ext)
            dir_agreement = float((np.sign(diff_amb) == np.sign(diff_ext)).mean())

    if (Ext_corr >= spearman_thresh and
        ext_delta >= min_ext_change and
        ((diff_corr is not None and diff_corr >= diff_corr_thresh) or dir_agreement >= dir_agree_thresh)):
        return True

    return False


def power_causes_ambient_spike(amb_vals, it_vals, spearman_thresh=0.5, min_it_change=0.5,
                                diff_corr_thresh=0.3, dir_agree_thresh=0.6):
    """Return (flag, info) if IT power change likely caused the ambient spike.

    We compute multiple measures and prefer diff or lagged correlation when available:
    - level Spearman on raw values
    - Spearman on first differences
    - best lagged Spearman across small lags (-2..2)

    Return:
        (bool, dict) where dict contains measured metrics and decision reason
    """
    amb = np.asarray(amb_vals, dtype=float)
    it = np.asarray(it_vals, dtype=float)
    mask = (~np.isnan(amb)) & (~np.isnan(it))
    amb = amb[mask]
    it = it[mask]

    info = {
        'IT_corr': None,
        'diff_corr': None,
        'dir_agreement': None,
        'it_delta': None,
        'best_lag_corr': None,
        'best_lag': None,
        'decision': None
    }

    if len(amb) < 5:
        return False, info

    IT_corr, _ = scipy.stats.spearmanr(amb, it)
    info['IT_corr'] = IT_corr

    it_delta = np.nanmax(it) - np.nanmin(it)
    info['it_delta'] = it_delta

    diff_corr = None
    dir_agreement = 0.0
    if len(it) >= 4:
        diff_it = np.diff(it)
        diff_amb = np.diff(amb)
        if len(diff_it) >= 3 and np.nanstd(diff_it) > 0 and np.nanstd(diff_amb) > 0:
            diff_corr, _ = scipy.stats.spearmanr(diff_amb, diff_it)
            dir_agreement = float((np.sign(diff_amb) == np.sign(diff_it)).mean())
            info['diff_corr'] = diff_corr
            info['dir_agreement'] = dir_agreement

    # compute best lagged correlation
    best_lag_corr = None
    best_lag = None
    max_lag = 2
    if len(it) >= 5:
        for lag in range(-max_lag, max_lag + 1):
            if lag == 0:
                vals_a = amb
                vals_b = it
            elif lag > 0:
                if len(amb) - lag < 5:
                    continue
                vals_a = amb[:-lag]
                vals_b = it[lag:]
            else:
                l = abs(lag)
                if len(amb) - l < 5:
                    continue
                vals_a = amb[l:]
                vals_b = it[:-l]

            try:
                c, _ = scipy.stats.spearmanr(vals_a, vals_b)
            except Exception:
                c = None
            if c is not None and not np.isnan(c):
                if best_lag_corr is None or abs(c) > abs(best_lag_corr):
                    best_lag_corr = c
                    best_lag = lag
    info['best_lag_corr'] = best_lag_corr
    info['best_lag'] = best_lag

    # Decision logic: require meaningful IT change and one of the correlation signals
    reason = None
    if it_delta >= min_it_change:
        if diff_corr is not None and abs(diff_corr) >= diff_corr_thresh:
            reason = 'diff_corr'
        elif best_lag_corr is not None and abs(best_lag_corr) >= diff_corr_thresh:
            reason = f'lag_{best_lag}'
        elif dir_agreement is not None and dir_agreement >= dir_agree_thresh:
            reason = 'dir_agreement'
        elif IT_corr is not None and abs(IT_corr) >= spearman_thresh:
            reason = 'level_corr'

    if reason:
        info['decision'] = reason
        return True, info

    return False, info
