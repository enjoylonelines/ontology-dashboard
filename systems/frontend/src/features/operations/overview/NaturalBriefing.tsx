import { useEffect, useRef, useState } from "react";
import { createOperationsAgentReviewSummary, getOperationsAgentReviewSummary } from "../../../api";
import type { OperationsAgentReviewSummary, OperationsAgentReviewSummaryResponse } from "../api/operationsContracts";
import { briefRows, relativeRecordTime, referenceLabels, readerLimitations } from "../../../standalone/briefFormat.js";
import { BriefingEvidencePanel } from "./BriefingEvidencePanel";
import "./NaturalBriefing.css";

type EvidenceGap = { field: string; reason: string; ownerDomain?: string; owner_domain?: string };
type Props = {
  projectId: string; workspaceId: string; assetId: string; eventId: string | null;
  datasetVersionId?: string | null; observedAt?: string | null;
  role: "process_engineer" | "maintenance_technician" | "process_manager";
  canGenerate?: boolean; revision?: string;
  providedResponse?: OperationsAgentReviewSummaryResponse;
  workflowRefresh?: NaturalBriefingRefreshState | null;
  evidenceGaps?: EvidenceGap[];
};

export type NaturalBriefingRefreshState = {
  token: string | number;
  state: "pending" | "failed" | "completed";
};

// A new selection is a new instance: old prose and pending responses cannot cross it.
export function NaturalBriefing(props: Props) {
  const revealed = useRef(new Set<string>());
  const dataset = props.eventId?.startsWith("FILE#") ? props.eventId.split("#")[1] : props.datasetVersionId;
  return <Briefing revealed={revealed.current} key={JSON.stringify([props.projectId, props.workspaceId, props.assetId,
    props.eventId?.startsWith("FILE#") ? dataset : props.eventId, props.role, props.revision, props.canGenerate, props.providedResponse?.trace.materialization?.summary_key, props.providedResponse?.trace.materialization?.status])} {...props} datasetVersionId={dataset}/>;
}

function accepted(response: OperationsAgentReviewSummaryResponse, assetId: string) {
  const summary = response.summary;
  const status = response.trace.materialization?.status;
  const stored = status === "ready" || status === "fallback" || status === "stale";
  return summary?.asset_id === assetId && stored && !response.trace.fallback ? summary : null;
}

function statusLabel(response: OperationsAgentReviewSummaryResponse, summary: OperationsAgentReviewSummary | null, hasEvidenceGaps = false) {
  if (!summary) {
    if (response.trace.materialization?.status === "pending") {
      return hasEvidenceGaps ? "근거 보완 후 생성" : "LLM 응답 생성 중";
    }
    if (response.trace.fallback) {
      if (response.trace.reason === "summary_validation_failed") {
        return "생성한 설명이 현재 근거 확인 규칙과 일치하지 않아 표시하지 않았습니다. 이 설명은 현재 판단에 사용하지 않습니다. 아래 확인이 필요한 데이터를 점검한 뒤 필요하면 브리핑을 다시 요청할 수 있습니다.";
      }
      if (response.trace.reason === "agent_review_summary_provider_disabled") {
        return "LLM 응답 생성 불가 · 설비 상태와 점검 기록 확인 필요";
      }
      return "현재 설비 상태와 점검 기록을 바탕으로 신뢰할 수 있는 브리핑을 만들지 못했습니다. 이 설명은 보여드리지 않고 현재 판단에도 사용하지 않습니다. 근거를 확인한 뒤 필요하면 브리핑을 다시 요청할 수 있습니다.";
    }
    return "현재 근거의 브리핑이 아직 없습니다. 현재 근거가 준비된 뒤 다시 조회하거나 브리핑 생성을 요청하세요.";
  }
  return response.trace.materialization?.status === "fallback" || response.trace.fallback || summary.mode !== "llm"
    ? "저장된 보조 브리핑 · LLM 응답 검증 실패 시 기준 근거로 구성"
    : response.trace.historical_available && !response.trace.current_ready
      ? "저장된 브리핑 · 이전 업무 시점 기준"
      : response.trace.current_ready
        ? "저장된 브리핑 · 현재 근거 기준"
        : "저장된 브리핑 · 준비 상태 확인 필요";
}

function evidenceGapLabel(gap: { field: string; reason: string }) {
  const reason = gap.reason.split(":", 1)[0];
  if (gap.field.includes("canonical_evidence") || reason === "canonical_evidence_missing_or_unresolved") return "원본 판단 근거";
  if (reason === "maintenance_context_missing_or_unresolved") return "정비 이력과 작업 조건";
  if (reason === "operation_context_missing_or_unresolved") return "생산 일정과 작업 조건";
  if (reason === "criticality_missing_or_unresolved" || reason === "criticality_basis_missing_or_unresolved") return "설비 중요도 기준";
  if (reason === "review_priority_inputs_missing_or_unresolved") return "검토 우선순위 산정 기준";
  if (reason === "field_inspection_location_reference_unavailable") return "현장 점검 위치 기준";
  if (reason === "adapter_context_unavailable") return "연결된 업무 맥락";
  return "브리핑 판단에 필요한 연결 근거";
}

function evidenceGapMessage(gap: { field: string; reason: string }) {
  const label = evidenceGapLabel(gap);
  return label === "원본 판단 근거" ? `${label}가 연결되지 않았습니다.` : `${label}이 연결되지 않았습니다.`;
}

function responseObservedAt(response: OperationsAgentReviewSummaryResponse, fallback?: string | null) {
  return response.trace.materialization?.decision_as_of ?? response.trace.materialization?.generated_at ?? fallback ?? null;
}

function Briefing(props: Props & { revealed: Set<string> }) {
  const supported = props.workspaceId === "manufacturing-demo" && Boolean(props.eventId);
  const [summaryKey, setSummaryKey] = useState<string | undefined>();
  const [summary, setSummary] = useState<OperationsAgentReviewSummary | null>(null);
  const [evidenceGaps, setEvidenceGaps] = useState<EvidenceGap[]>(() => props.evidenceGaps ?? []);
  const [materializationStatus, setMaterializationStatus] = useState<string | undefined>();
  const [status, setStatus] = useState(supported ? "브리핑 조회 중" : "선택한 근거에 연결된 브리핑이 없습니다.");
  const [busy, setBusy] = useState(supported);
  const [basis, setBasis] = useState({eventId: props.eventId, observedAt: props.observedAt});
  const controllerRef = useRef<AbortController | null>(null);
  const input = { assetId: props.assetId, eventId: props.eventId, projectId: props.projectId,
    datasetVersionId: props.datasetVersionId, historyWindow: "24h" };

  async function read(controller: AbortController) {
    const response = await getOperationsAgentReviewSummary({ ...input, signal: controller.signal });
    if (controller.signal.aborted) return;
    const next = accepted(response, props.assetId);
    const gaps = next ? [] : response.trace.evidence_gaps?.length ? response.trace.evidence_gaps : props.evidenceGaps ?? [];
    setSummary(next);
    setEvidenceGaps(gaps);
    setMaterializationStatus(response.trace.materialization?.status);
    setSummaryKey(next ? response.trace.materialization?.summary_key : undefined);
    if (next) setBasis({eventId: props.eventId, observedAt: responseObservedAt(response, props.observedAt)});
    setStatus(statusLabel(response, next, gaps.length > 0));
  }
  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    if (props.providedResponse) {
      const next = accepted(props.providedResponse, props.assetId);
      const gaps = next ? [] : props.providedResponse.trace.evidence_gaps?.length ? props.providedResponse.trace.evidence_gaps : props.evidenceGaps ?? [];
      setSummary(next); setSummaryKey(next ? props.providedResponse.trace.materialization?.summary_key : undefined);
      setEvidenceGaps(gaps); setMaterializationStatus(props.providedResponse.trace.materialization?.status);
      if (next) setBasis({eventId: props.eventId, observedAt: responseObservedAt(props.providedResponse, props.observedAt)});
      setBusy(false);
      setStatus(statusLabel(props.providedResponse, next, gaps.length > 0));
    } else if (supported) void read(controller).catch(() => {
      if (!controller.signal.aborted) setStatus("브리핑을 불러오지 못했습니다. 판단 근거는 계속 확인할 수 있습니다.");
    }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!props.workflowRefresh) return;
    if (props.workflowRefresh.state === "pending") {
      setBusy(true);
      setStatus(summary
        ? "최신 작업 기준으로 브리핑을 갱신 중입니다. 이전 저장본을 표시합니다."
        : "작업은 접수됐고 최신 브리핑을 생성 중입니다.");
    } else if (props.workflowRefresh.state === "failed") {
      setBusy(false);
      setStatus(summary
        ? "최신 브리핑 생성에 실패했습니다. 이전 저장본을 표시합니다."
        : "최신 브리핑 생성에 실패했습니다. 저장된 브리핑이 아직 없습니다.");
    } else {
      setBusy(false);
      setStatus(summary
        ? "최신 작업을 저장했습니다. 저장된 브리핑을 다시 확인합니다."
        : "최신 작업을 저장했습니다. 브리핑을 다시 조회합니다.");
    }
  }, [props.workflowRefresh?.token, props.workflowRefresh?.state]);

  async function generate() {
    const controller = controllerRef.current;
    if (busy || !props.canGenerate || !supported || !controller || controller.signal.aborted) return;
    setBasis({eventId: props.eventId, observedAt: props.observedAt});
    setBusy(true);
    setStatus(summary
      ? "현재 업무 시점으로 브리핑을 갱신 중입니다. 이전 저장본을 표시합니다."
      : "현재 업무 시점으로 LLM 응답 생성 중");
    try {
      const result = await createOperationsAgentReviewSummary({ ...input, signal: controller.signal });
      if (controller.signal.aborted) return;
      if (!accepted(result, props.assetId)) {
        setSummary(null);
        setSummaryKey(undefined);
        const gaps = result.trace.evidence_gaps?.length ? result.trace.evidence_gaps : props.evidenceGaps ?? [];
        setEvidenceGaps(gaps); setMaterializationStatus(result.trace.materialization?.status);
        setStatus(statusLabel(result, null, gaps.length > 0));
      } else {
        const next = accepted(result, props.assetId);
        setSummary(next);
        setSummaryKey(next ? result.trace.materialization?.summary_key : undefined);
        if (next) setBasis({eventId: props.eventId, observedAt: responseObservedAt(result, props.observedAt)});
        setStatus(statusLabel(result, next));
        await read(controller).catch(() => undefined);
      }
    } catch (error) {
      if (!controller.signal.aborted) setStatus(error instanceof Error && /429|rate.limit|잠시 후/.test(error.message)
        ? "생성 요청이 많습니다. 약 1분 후 다시 시도해 주세요."
        : "브리핑을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }

  const quote = summary?.role_summaries.find(item => item.role === props.role)?.quote?.trim() || summary?.summary || "";
  const rows = briefRows(quote, summary?.source_refs ?? []);
  const visibleEvidenceGaps = [...new Map(evidenceGaps.map(gap => [evidenceGapLabel(gap), gap])).values()];
  const evidenceState = visibleEvidenceGaps.length ? `필수 근거 ${visibleEvidenceGaps.length}건 미확인` : "판단 근거 연결됨";
  const generating = !summary && !visibleEvidenceGaps.length && (busy || materializationStatus === "pending" || props.workflowRefresh?.state === "pending");
  const llmState = summary ? "사용 가능" : visibleEvidenceGaps.length ? "근거 보완 후 생성" : generating ? "생성 중" : "생성 대기";
  const workflowBadge = props.workflowRefresh?.state === "pending" ? "갱신 중" : props.workflowRefresh?.state === "failed" ? "갱신 실패" : "";
  const evidenceScope = { ...props, eventId: basis.eventId, observedAt: basis.observedAt, expectedSummaryKey: summaryKey, onEvidenceChanged: () => {
        setBusy(false);
        setSummary(null);
        setSummaryKey(undefined);
        setBasis({ eventId: props.eventId, observedAt: props.observedAt });
        setStatus("근거가 변경되어 이전 브리핑을 숨겼습니다. 현재 근거 기준 브리핑을 다시 조회해 주세요.");
      } };
  return <section className="natural-briefing" aria-label="LLM 응답" aria-busy={busy}>
    <div className="natural-briefing-heading"><strong>LLM 응답</strong>
      {workflowBadge ? <span className={`natural-briefing-refresh is-${props.workflowRefresh?.state}`}>{workflowBadge}</span> : null}
      {supported && props.canGenerate ? <button type="button" disabled={busy} onClick={() => void generate()}>{busy ? "처리 중" : summary ? "다시 생성" : "LLM 응답 생성"}</button> : null}
    </div>
    <dl className="natural-briefing-state" aria-label="LLM과 근거 상태"><div><dt>근거 상태</dt><dd className={visibleEvidenceGaps.length ? "is-hold" : "is-ready"}>{evidenceState}</dd></div><div><dt>LLM 응답</dt><dd className={generating ? "is-generating" : visibleEvidenceGaps.length ? "is-hold" : "is-ready"}>{llmState}</dd></div></dl>
    {generating ? <div className="natural-briefing-generation" role="status"><span aria-hidden="true"><i/><i/><i/></span>근거 기반 응답 생성 중</div> : null}
    {status !== llmState ? <p className="natural-briefing-status" role="status">{status}</p> : null}
    {!summary && visibleEvidenceGaps.length ? <section className="natural-briefing-gaps" aria-label="확인할 데이터"><strong>확인할 데이터</strong><ul>{visibleEvidenceGaps.map(gap => <li key={`${gap.field}:${gap.reason}`}>{evidenceGapMessage(gap)}</li>)}</ul><p>원문 근거 확인 후 재요청</p></section> : null}
    {summary ? <StreamingProse key={JSON.stringify([props.assetId, basis.eventId, props.role, quote])}
      rows={rows} identity={JSON.stringify([props.projectId, props.workspaceId, props.assetId, basis.eventId, props.role, quote])}
      revealed={props.revealed} evidenceScope={evidenceScope}/> : null}
    {summary ? <div className="natural-briefing-basis">{props.assetId}{basis.observedAt ? <> · 관측 기준 <time dateTime={basis.observedAt}>{relativeRecordTime(basis.observedAt)}</time></> : null}
      {summary.limitations.length ? <details><summary>해석 시 유의사항</summary>{readerLimitations(summary.limitations).map((text, i) => <p key={i}>{text}</p>)}</details> : null}
    </div> : null}
  </section>;
}

// Reveal already validated prose locally; this does not stream unvalidated model tokens.
function StreamingProse({ rows, identity, revealed, evidenceScope }: {
  rows: ReturnType<typeof briefRows>; identity: string; revealed: Set<string>; evidenceScope: Props & { expectedSummaryKey?: string; onEvidenceChanged?: () => void };
}) {
  const total = rows.reduce((n, row) => n + row.parts.reduce((m, part) => m + Array.from(part.text).length, 0), 0);
  const [count, setCount] = useState(() => revealed.has(identity) || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? total : 0);
  useEffect(() => {
    const preference = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    let frame = 0;
    const finish = () => { cancelAnimationFrame(frame); revealed.add(identity); setCount(total); };
    const onPreference = () => { if (preference?.matches) finish(); };
    if (revealed.has(identity) || preference?.matches) { finish(); return; }
    const duration = Math.min(4800, Math.max(900, total * 12));
    let start: number | null = null;
    const step = (now: number) => {
      start ??= now;
      const progress = Math.min(1, (now - start) / duration);
      setCount(Math.floor(total * progress));
      if (progress < 1) frame = requestAnimationFrame(step);
      else revealed.add(identity);
    };
    frame = requestAnimationFrame(step);
    preference?.addEventListener("change", onPreference);
    return () => { cancelAnimationFrame(frame); preference?.removeEventListener("change", onPreference); };
  }, [identity, total, revealed]);
  let offset = 0;
  return <div className="natural-briefing-prose" data-streaming={count < total}>
    <div className="natural-briefing-accessible">{rows.map((row, i) => <p key={i}>{row.parts.map(p => p.text).join("")}</p>)}</div>
    {rows.map((row, index) => {
      const beginning = offset;
      const length = row.parts.reduce((n, part) => n + Array.from(part.text).length, 0);
      const end = beginning + length;
      const cursorHere = count >= beginning && (count < end || (index === rows.length - 1 && count === total));
      return <div className={`natural-briefing-line is-${row.kind ?? "paragraph"}`} key={index}>
        <p aria-hidden="true">{row.parts.map((part, i) => {
          const letters = Array.from(part.text);
          const visible = Math.max(0, Math.min(letters.length, count - offset));
          const cursor = cursorHere && count >= offset && (count < offset + letters.length || (i === row.parts.length - 1 && count === end));
          offset += letters.length;
          const Tag = part.weight === "700" ? "strong" : "span";
          return <Tag key={i}>{letters.slice(0, visible).join("")}{cursor ? <span className="natural-briefing-cursor"/> : null}<span style={{visibility:"hidden"}}>{letters.slice(visible).join("")}</span></Tag>;
        })}</p>
        {row.refs.map((ref, i) => <EvidenceDisclosure key={i} visible={count >= end} refs={ref.text} scope={evidenceScope}/>)}
      </div>;
    })}
  </div>;
}


function EvidenceDisclosure({ visible, refs, scope, label = "근거" }: { visible: boolean; refs: string; label?: string; scope: Props & { expectedSummaryKey?: string; onEvidenceChanged?: () => void } }) {
  const [open, setOpen] = useState(false);
  return <details style={{ visibility: visible ? "visible" : "hidden" }} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>{label}</summary><p>{referenceLabels(refs).join(" · ")}</p>
    {open && !scope.providedResponse ? <BriefingEvidencePanel {...scope} refs={refs.split("\n").filter(Boolean)}/> : null}
  </details>;
}
