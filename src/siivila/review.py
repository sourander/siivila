"""Interactive local review mode for verifying and editing criterion evidence."""

import argparse
import json
import sys
from pathlib import Path

from .criteria import (
    CriterionResult,
    SynthesisInstance,
    aggregate_status,
    load_criteria,
    sentence_lookup,
)
from .extraction import SubmissionExtraction, extract_submission

EXIT_USAGE_ERROR = 2


def resolve_pdf_dir(results_dir: Path, pdf_dir: Path | None = None) -> Path:
    """Resolve the directory containing source PDFs for a results directory."""
    if pdf_dir is not None:
        return pdf_dir
    manifest_path = results_dir / "manifest.json"
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            input_dir = data.get("input_dir")
            if input_dir and Path(input_dir).is_dir():
                return Path(input_dir)
        except Exception:
            pass
    if any(results_dir.glob("*.pdf")):
        return results_dir
    return results_dir.parent


def discover_review_targets(
    results_dir: Path, pdf_dir: Path | None = None
) -> tuple[list[str], dict[str, str]]:
    """Return sorted submission stems and a {criterion_id: version} mapping."""
    resolved_pdf_dir = resolve_pdf_dir(results_dir, pdf_dir)
    stems: set[str] = {p.stem for p in resolved_pdf_dir.glob("*.pdf")}
    criteria_versions: dict[str, str] = {}
    try:
        for crit in load_criteria():
            criteria_versions[crit.id] = crit.version
    except Exception:
        pass

    for path in sorted(results_dir.glob("*.*.json")):
        if path.name == "manifest.json":
            continue
        parts = path.name.rsplit(".", 2)
        if len(parts) == 3:
            stem, criterion_id, _ = parts
            stems.add(stem)
            if criterion_id not in criteria_versions:
                try:
                    res = CriterionResult.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                    criteria_versions[criterion_id] = res.criterion_version
                except Exception:
                    criteria_versions[criterion_id] = "1.0"

    return sorted(stems), dict(sorted(criteria_versions.items()))


def result_file_path(results_dir: Path, stem: str, criterion_id: str) -> Path:
    """Return the path to <stem>.<criterion>.json inside results_dir."""
    return results_dir / f"{stem}.{criterion_id}.json"


def load_or_init_result(
    results_dir: Path,
    stem: str,
    criterion_id: str,
    criterion_version: str = "1.1",
) -> CriterionResult:
    """Load an existing CriterionResult JSON or initialize an empty one."""
    path = result_file_path(results_dir, stem, criterion_id)
    if path.is_file():
        return CriterionResult.model_validate_json(path.read_text(encoding="utf-8"))
    return CriterionResult(
        submission_id=f"{stem}.pdf",
        criterion_id=criterion_id,
        criterion_version=criterion_version,
        status="not_met",
        instances=[],
    )


def _persist_result(results_dir: Path, result: CriterionResult) -> CriterionResult:
    result.status = aggregate_status(result.instances)
    stem = Path(result.submission_id).stem
    path = result_file_path(results_dir, stem, result.criterion_id)
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result


def save_instance(
    results_dir: Path,
    result: CriterionResult,
    extraction: SubmissionExtraction,
    sentence_ids: list[str],
    rationale: str,
    uncertain: bool = False,
    index: int | None = None,
) -> CriterionResult:
    """Add or update an evidence instance with deterministic quotes and save."""
    lookup = sentence_lookup(extraction)
    selected = set(sentence_ids)
    ordered_ids = [sid for sid in lookup if sid in selected]
    if not ordered_ids:
        raise ValueError("At least one valid sentence identifier is required.")
    instance = SynthesisInstance(
        sentence_ids=ordered_ids,
        quotes=[lookup[sid] for sid in ordered_ids],
        classification=result.criterion_id,
        rationale=rationale.strip(),
        uncertain=uncertain,
    )
    if index is None:
        result.instances.append(instance)
    else:
        result.instances[index] = instance
    return _persist_result(results_dir, result)


def delete_instance(
    results_dir: Path, result: CriterionResult, index: int
) -> CriterionResult:
    """Remove an evidence instance by index, recompute status, and save."""
    result.instances.pop(index)
    return _persist_result(results_dir, result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review",
        description=(
            "Launch the interactive NiceGUI review interface for inspecting "
            "and editing per-criterion evidence."
        ),
    )
    parser.add_argument(
        "--dir",
        required=True,
        type=Path,
        help="Directory containing <stem>.<criterion>.json result files.",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=None,
        help="Optional directory containing source PDFs (defaults to manifest input_dir).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Local port for the NiceGUI web interface (default: 8080).",
    )
    return parser


def build_review_app(results_dir: Path, pdf_dir: Path) -> None:
    """Register the NiceGUI review page for the given directories."""
    from nicegui import ui

    stems, criteria_versions = discover_review_targets(results_dir, pdf_dir)
    if not stems:
        raise RuntimeError(f"No submissions or result files found in {results_dir}")
    if not criteria_versions:
        criteria_versions = {"synthesis": "1.1"}

    extractions: dict[str, SubmissionExtraction] = {}

    def get_extraction(stem: str) -> SubmissionExtraction | None:
        if stem not in extractions:
            pdf_path = pdf_dir / f"{stem}.pdf"
            if not pdf_path.is_file():
                return None
            outcome = extract_submission(pdf_path)
            if outcome.extraction is not None:
                extractions[stem] = outcome.extraction
        return extractions.get(stem)

    @ui.page("/")
    def index_page() -> None:
        state: dict = {
            "stem": stems[0],
            "criterion": next(iter(criteria_versions)),
            "editing_index": None,
            "selected_sids": [],
            "rationale": "",
            "uncertain": False,
        }
        sent_labels: dict[str, ui.label] = {}
        sent_to_instances: dict[str, list[tuple[int, SynthesisInstance]]] = {}

        def current_result() -> CriterionResult:
            crit = state["criterion"]
            return load_or_init_result(
                results_dir,
                state["stem"],
                crit,
                criteria_versions.get(crit, "1.1"),
            )

        def sentence_classes(sid: str) -> str:
            matches = sent_to_instances.get(sid, [])
            if sid in state["selected_sids"]:
                style = "bg-sky-200 ring-2 ring-sky-600 font-medium"
            elif any(inst.uncertain for _, inst in matches):
                style = "bg-amber-200 hover:bg-amber-300"
            elif matches:
                style = "bg-emerald-200 hover:bg-emerald-300"
            else:
                style = "hover:bg-slate-100"
            return f"inline cursor-pointer rounded px-1 py-0.5 mr-1 transition-colors {style}"

        def update_selection_ui() -> None:
            for sid, lbl in sent_labels.items():
                lbl.classes(replace=sentence_classes(sid))
            refresh_sidebar()

        def reset_editor() -> None:
            state["editing_index"] = None
            state["selected_sids"] = []
            state["rationale"] = ""
            state["uncertain"] = False

        def select_for_edit(idx: int, inst: SynthesisInstance) -> None:
            state["editing_index"] = idx
            state["selected_sids"] = list(inst.sentence_ids)
            state["rationale"] = inst.rationale
            state["uncertain"] = inst.uncertain
            update_selection_ui()

        def toggle_sentence(sid: str) -> None:
            ext = get_extraction(state["stem"])
            lookup = sentence_lookup(ext) if ext else {}
            current = set(state["selected_sids"])
            if sid in current:
                current.remove(sid)
            else:
                current.add(sid)
            state["selected_sids"] = (
                [s for s in lookup if s in current]
                if lookup
                else sorted(current)
            )
            update_selection_ui()

        def handle_save() -> None:
            ext = get_extraction(state["stem"])
            if ext is None:
                ui.notify("Cannot save: source PDF extraction unavailable.", type="negative")
                return
            if not state["selected_sids"]:
                ui.notify("Select at least one sentence in the diary first.", type="warning")
                return
            res = current_result()
            save_instance(
                results_dir,
                res,
                ext,
                state["selected_sids"],
                state["rationale"],
                state["uncertain"],
                index=state["editing_index"],
            )
            ui.notify("Saved to JSON.", type="positive")
            reset_editor()
            refresh_all()

        def handle_delete(idx: int) -> None:
            res = current_result()
            delete_instance(results_dir, res, idx)
            if state["editing_index"] == idx:
                reset_editor()
            ui.notify(f"Deleted instance #{idx + 1}.", type="info")
            refresh_all()

        with ui.header().classes("items-center justify-between bg-slate-900 text-white px-6 py-3"):
            ui.label("Siivilä Review").classes("text-lg font-bold")
            with ui.row().classes("items-center gap-4"):
                ui.select(
                    options=stems,
                    value=state["stem"],
                    label="Submission",
                    on_change=lambda e: (
                        state.update(stem=e.value),
                        reset_editor(),
                        refresh_all(),
                    ),
                ).props("dark dense outlined").classes("w-64")
                ui.select(
                    options=list(criteria_versions.keys()),
                    value=state["criterion"],
                    label="Criterion",
                    on_change=lambda e: (
                        state.update(criterion=e.value),
                        reset_editor(),
                        refresh_all(),
                    ),
                ).props("dark dense outlined").classes("w-48")
                status_container = ui.row().classes("items-center")

        with ui.row().classes("w-full no-wrap items-start gap-4 p-4"):
            diary_container = ui.column().classes(
                "w-7/12 bg-white rounded shadow p-6 max-h-[86vh] overflow-y-auto"
            )
            sidebar_container = ui.column().classes(
                "w-5/12 gap-4 max-h-[86vh] overflow-y-auto"
            )

        def refresh_sidebar() -> None:
            res = current_result()
            ext = get_extraction(state["stem"])
            lookup = sentence_lookup(ext) if ext else {}

            sidebar_container.clear()
            with sidebar_container:
                with ui.card().classes("w-full p-4 bg-white"):
                    mode_title = (
                        f"Editing Instance #{state['editing_index'] + 1}"
                        if state["editing_index"] is not None
                        else "Add Evidence Instance"
                    )
                    ui.label(mode_title).classes("font-bold text-slate-800")
                    ui.label(
                        "Selected sentences: "
                        + (
                            ", ".join(state["selected_sids"])
                            if state["selected_sids"]
                            else "(click sentences in the diary)"
                        )
                    ).classes("text-xs font-mono text-slate-600")

                    if state["selected_sids"] and lookup:
                        with ui.column().classes("w-full bg-slate-50 p-2 rounded gap-1"):
                            for sid in state["selected_sids"]:
                                if sid in lookup:
                                    ui.label(f"{sid}: {lookup[sid]}").classes(
                                        "text-xs italic text-slate-700"
                                    )

                    ui.checkbox(
                        "Uncertain (borderline finding)",
                        value=state["uncertain"],
                        on_change=lambda e: state.update(uncertain=e.value),
                    ).classes("text-sm")
                    ui.textarea(
                        label="Rationale",
                        value=state["rationale"],
                        on_change=lambda e: state.update(rationale=e.value),
                    ).classes("w-full text-sm").props("outlined dense rows=3")

                    with ui.row().classes("gap-2 mt-1"):
                        ui.button("Save Instance", on_click=handle_save).props(
                            "color=primary dense"
                        )
                        ui.button(
                            "Clear / Cancel",
                            on_click=lambda: (reset_editor(), update_selection_ui()),
                        ).props("flat dense")

                ui.label(f"Evidence Instances ({len(res.instances)})").classes(
                    "font-bold text-slate-700 mt-2"
                )
                for idx, inst in enumerate(res.instances):
                    is_editing = state["editing_index"] == idx
                    border = "ring-2 ring-sky-500" if is_editing else ""
                    with ui.card().classes(f"w-full p-3 bg-white {border}"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(f"#{idx + 1}").classes("font-bold text-sm")
                                ui.label(", ".join(inst.sentence_ids)).classes(
                                    "text-xs font-mono bg-slate-100 px-2 py-0.5 rounded"
                                )
                                if inst.uncertain:
                                    ui.label("UNCERTAIN").classes(
                                        "text-[10px] font-bold bg-amber-200 text-amber-900 px-1.5 py-0.5 rounded"
                                    )
                            with ui.row().classes("gap-1"):
                                ui.button(
                                    "Edit",
                                    on_click=lambda _, i=idx, item=inst: select_for_edit(
                                        i, item
                                    ),
                                ).props("flat dense size=sm color=primary")
                                ui.button(
                                    "Delete",
                                    on_click=lambda _, i=idx: handle_delete(i),
                                ).props("flat dense size=sm color=negative")
                        for quote in inst.quotes:
                            ui.label(f"“{quote}”").classes(
                                "text-xs italic text-slate-600 border-l-2 border-slate-300 pl-2"
                            )
                        if inst.rationale:
                            ui.label(inst.rationale).classes("text-xs text-slate-800 mt-1")

        def refresh_all() -> None:
            res = current_result()
            ext = get_extraction(state["stem"])

            status_container.clear()
            with status_container:
                color = {
                    "met": "bg-emerald-600",
                    "uncertain": "bg-amber-600",
                    "not_met": "bg-rose-600",
                }.get(res.status, "bg-slate-600")
                ui.label(
                    f"{res.status.upper()} ({len(res.instances)} instances)"
                ).classes(f"{color} text-white text-xs font-bold px-3 py-1 rounded")

            sent_to_instances.clear()
            for idx, inst in enumerate(res.instances):
                for sid in inst.sentence_ids:
                    sent_to_instances.setdefault(sid, []).append((idx, inst))

            sent_labels.clear()
            diary_container.clear()
            with diary_container:
                if ext is None:
                    ui.label(
                        f"PDF not found at {pdf_dir / (state['stem'] + '.pdf')}"
                    ).classes("text-rose-600 font-semibold")
                else:
                    for topic in ext.topics:
                        ui.label(topic.title).classes(
                            "text-xl font-bold text-slate-900 mt-4 mb-2 border-b pb-1 w-full"
                        )
                        current_sub: str | None = None
                        for paragraph in topic.paragraphs:
                            if paragraph.subheading != current_sub:
                                current_sub = paragraph.subheading
                                if current_sub is not None:
                                    ui.label(current_sub).classes(
                                        "text-md font-semibold text-slate-700 mt-3 mb-1"
                                    )
                            with ui.element("div").classes(
                                "text-sm leading-relaxed text-slate-800 mb-3"
                            ):
                                for sentence in paragraph.sentences:
                                    sid = sentence.id
                                    text = paragraph.text[sentence.start : sentence.end]
                                    matches = sent_to_instances.get(sid, [])
                                    badges = "".join(f"#{i + 1}" for i, _ in matches)
                                    prefix = f"[{sid}{(' ' + badges) if badges else ''}] "
                                    lbl = ui.label(f"{prefix}{text}").classes(
                                        sentence_classes(sid)
                                    )
                                    lbl.on("click", lambda _, s=sid: toggle_sentence(s))
                                    sent_labels[sid] = lbl

                    if ext.references:
                        ui.label("Lähteet / References").classes(
                            "text-xl font-bold text-slate-900 mt-6 mb-2 border-b pb-1 w-full"
                        )
                        for ref in ext.references:
                            num = f"[{ref.number}] " if ref.number is not None else ""
                            ui.label(f"{num}{ref.text}").classes(
                                "text-xs text-slate-600 mb-1"
                            )

            refresh_sidebar()

        refresh_all()


def run_ui(results_dir: Path, pdf_dir: Path, port: int = 8080) -> None:
    """Start the NiceGUI review application."""
    from nicegui import ui

    build_review_app(results_dir, pdf_dir)
    ui.run(title="Siivilä Review", port=port, reload=False)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.dir.is_dir():
        print(
            f"review: error: --dir does not exist or is not a directory: {args.dir}",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    if args.pdf_dir is not None and not args.pdf_dir.is_dir():
        print(
            f"review: error: --pdf-dir does not exist or is not a directory: {args.pdf_dir}",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR

    pdf_dir = resolve_pdf_dir(args.dir, args.pdf_dir)
    run_ui(args.dir, pdf_dir, port=args.port)
    return 0
