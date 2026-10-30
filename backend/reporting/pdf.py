"""PDF reports (ReportLab). Content is taken verbatim from stored run / experiment records."""
from __future__ import annotations

import io
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SAGE = colors.HexColor("#779477")
INK = colors.HexColor("#26372D")


def _doc(title: str):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=title)
    st = getSampleStyleSheet()
    st["Title"].textColor = INK
    st["Heading2"].textColor = INK
    return buf, doc, st


def _table(rows, widths=None):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), SAGE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d3c3")),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFEF7"), colors.HexColor("#EAF0E5")])]))
    return t


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}"
    if isinstance(v, (dict, list)):
        s = json.dumps(v, default=str)
        return s[:90] + ("…" if len(s) > 90 else "")
    return str(v)


def run_report_pdf(run: dict) -> bytes:
    buf, doc, st = _doc(f"ASTRA run {run['run_uid']}")
    el = [Paragraph(f"ASTRA {run['module'].upper()} — Mission Debrief", st["Title"]),
          Paragraph(f"Run {run['run_uid']} · controller {run['controller']} · seed {run['seed']} · status {run['status']}", st["Normal"]),
          Spacer(1, 6)]
    res = run.get("result") or {}
    el.append(Paragraph("Result", st["Heading2"]))
    el.append(_table([["Metric", "Value"]] + [[k, _fmt(v)] for k, v in res.items() if k not in ("phase_history", "touchdown", "timeline")]))
    if res.get("touchdown"):
        el.append(Paragraph("Touchdown", st["Heading2"]))
        el.append(_table([["Quantity", "Value"]] + [[k, _fmt(v)] for k, v in res["touchdown"].items()]))
    if res.get("phase_history"):
        el.append(Paragraph("Phase history", st["Heading2"]))
        el.append(_table([["t [s]", "from", "to", "reason"]] + [[h["t"], h["from"], h["to"], h["reason"][:70]] for h in res["phase_history"]]))
    if run.get("decisions"):
        el.append(Paragraph("Decision audit", st["Heading2"]))
        el.append(_table([["id", "t [s]", "trigger", "decision", "outcome"]] +
                         [[d["event_id"], f"{d['t']:.1f}", d["trigger"][:40], d["decision"][:40],
                           _fmt(d.get("actual_outcome"))[:50]] for d in run["decisions"]]))
    el.append(Spacer(1, 8))
    el.append(Paragraph(f"Software: {_fmt(run.get('software_versions'))}", st["Normal"]))
    doc.build(el)
    return buf.getvalue()


def experiment_report_pdf(exp: dict) -> bytes:
    buf, doc, st = _doc(f"ASTRA experiment {exp['id']}")
    el = [Paragraph(f"ASTRA Experiment #{exp['id']}: {exp['name']}", st["Title"]),
          Paragraph(f"Status {exp['status']} · held-out {exp['held_out']} · trials/condition {exp['config'].get('trials')}", st["Normal"])]
    summ = exp.get("summary") or {}
    for g in summ.get("groups", []):
        pass
    if summ.get("table"):
        el.append(Paragraph("Results (completion rate with 95% Wilson CI; continuous metrics mean ± SD, n)", st["Heading2"]))
        rows = [["terrain", "condition", "controller", "n", "completion", "95% CI", "time [s]", "energy [Wh]", "violations"]]
        for r in summ["table"]:
            rows.append([r["terrain"], r["condition"], r["controller"], r["n"], f"{r['completion_rate']:.2f}",
                         f"[{r['ci_low']:.2f}, {r['ci_high']:.2f}]", r.get("time_str", "-"), r.get("energy_str", "-"),
                         r.get("violations_str", "-")])
        el.append(_table(rows))
    if summ.get("paired"):
        el.append(Paragraph("Paired comparisons (ASTRA vs FSM, matched seeds)", st["Heading2"]))
        rows = [["terrain", "condition", "metric", "n pairs", "mean diff", "test", "p"]]
        for p in summ["paired"]:
            rows.append([p["terrain"], p["condition"], p["metric"], p["n"], _fmt(p["mean_diff"]), p["test"], _fmt(p["p_value"])])
        el.append(_table(rows))
    el.append(Spacer(1, 8))
    el.append(Paragraph(f"Software: {_fmt(exp.get('software_versions'))}", st["Normal"]))
    doc.build(el)
    return buf.getvalue()
