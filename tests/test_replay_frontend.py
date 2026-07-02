from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_replay_tab_is_registered_and_verify_is_embedded() -> None:
    top_bar = (ROOT / "frontend/src/components/TopBar.tsx").read_text()
    app = (ROOT / "frontend/src/App.tsx").read_text()
    translations = (ROOT / "frontend/src/i18n/translations.ts").read_text()
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "id: 'replay'" in top_bar
    assert "id: 'verify'" not in top_bar
    assert "case 'replay': return <ReplayPanel />" in app
    assert "case 'verify'" not in app
    assert "tab.verify" not in app
    assert "function VerifyReplaySection" in replay_panel
    assert "<VerifyPanel embedded className=\"mt-3\" />" in replay_panel
    assert "'tab.verify': 'Verify'" in translations


def test_verify_panel_calls_replay_verify_endpoint() -> None:
    verify_panel = (ROOT / "frontend/src/components/VerifyPanel.tsx").read_text()

    assert "receipt.json path" in verify_panel
    assert "replay.redacted.json path" in verify_panel
    assert "fetch('/api/replay/verify'" in verify_panel
    assert "Signature and local hashes match." in verify_panel


def test_replay_panel_shows_skill_provenance_index() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "SkillProvenancePanel" in replay_panel
    assert "useApi<any>('/replay/skills'" in replay_panel
    assert "success_rate" in replay_panel
    assert "hash {skill.hash || 'unavailable'}" in replay_panel
    assert "first {formatDate(skill.first_used_at)}" in replay_panel
    assert "mutation receipts {(skill.mutation_receipts || []).length}" in replay_panel


def test_replay_panel_has_prd_list_filters_and_columns() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "RUN_FILTERS" in replay_panel
    assert "Successful" in replay_panel
    assert "Failed" in replay_panel
    assert "Has tools" in replay_panel
    assert "File changes" in replay_panel
    assert "High cost" in replay_panel
    assert "runMatchesFilter(run, filter)" in replay_panel
    assert "run.counts.files_changed" in replay_panel
    assert "run.redaction_status.replaceAll" in replay_panel


def test_replay_detail_has_proof_score_and_timeline_metadata() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "function ProofScoreCard" in replay_panel
    assert "proofScore(detail)" in replay_panel
    assert "local hashes" in replay_panel
    assert "Status: {event.status}" in replay_panel
    assert "Redaction: {event.redacted_content ? 'redacted' : 'summary only'}" in replay_panel
    assert "{compactTime(event.timestamp)}" in replay_panel


def test_replay_detail_has_collapsed_raw_trace_toggle() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "function RawTracePanel" in replay_panel
    assert "Show normalized trace" in replay_panel
    assert "Hide normalized trace" in replay_panel
    assert "<RawTracePanel detail={detail} />" in replay_panel


def test_replay_detail_has_share_card_preview() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "function ShareCardPreview" in replay_panel
    assert "Hermes Replay" in replay_panel
    assert "Replay hash: {run.hashes.redacted_replay_hash || 'Pending'}" in replay_panel
    assert "<ShareCardPreview detail={detail} />" in replay_panel


def test_replay_export_actions_include_local_unpublish() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "actionGroups" in replay_panel
    assert "Prepare" in replay_panel
    assert "Export" in replay_panel
    assert "Share Images" in replay_panel
    assert "Publish" in replay_panel
    assert "['Unpublish', '/publish', 'DELETE']" in replay_panel
    assert "['Record View', '/view']" in replay_panel
    assert "['Landscape PNG', '/share-card?card_format=landscape']" in replay_panel
    assert "['Square PNG', '/share-card?card_format=square']" in replay_panel
    assert "['Story PNG', '/share-card?card_format=story']" in replay_panel
    assert "method = 'POST'" in replay_panel


def test_replay_panel_shows_local_gallery_index() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "function ReplayGalleryPanel" in replay_panel
    assert "useApi<any>('/replay/gallery'" in replay_panel
    assert "Published Gallery" in replay_panel
    assert "Static index: {galleryPath}" in replay_panel
    assert "views {entry.view_count || 0} · forks {entry.fork_count || 0}" in replay_panel


def test_redaction_panel_shows_finding_type_summary() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "findingCounts" in replay_panel
    assert "'api_key'" in replay_panel
    assert "'bearer_token'" in replay_panel
    assert "'local_path'" in replay_panel
    assert "'raw_field'" in replay_panel


def test_replay_settings_warn_before_raw_logs_or_screenshots() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "Raw logs and screenshots can expose private prompts" in replay_panel
    assert "Safe Share Mode remains on for default exports" in replay_panel


def test_proof_artifacts_panel_has_type_filters() -> None:
    replay_panel = (ROOT / "frontend/src/components/ReplayPanel.tsx").read_text()

    assert "const [filter, setFilter] = useState('all')" in replay_panel
    assert "visibleArtifacts" in replay_panel
    assert "type.replaceAll('_', ' ')" in replay_panel
