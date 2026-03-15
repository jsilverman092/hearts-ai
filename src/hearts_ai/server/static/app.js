const SCHEMA_VERSION = 1;
const RECONNECT_DELAY_MS = 1500;
const DEFAULT_PACE_MS = 900;
const FAST_FORWARD_PACE_MS = 220;
const PASS_AUTOPLAY_DELAY_MS = 20;
const TRICK_HOLD_MS = 1500;
const BOT_OPTIONS = ["search_v1", "heuristic_v3", "heuristic_v2", "heuristic", "random"];

const appState = {
  tableCode: null,
  playerSecret: null,
  displayName: "",
  ws: null,
  reconnectTimer: null,
  advanceTimer: null,
  trickHoldTimer: null,
  advanceInFlight: false,
  paceMs: DEFAULT_PACE_MS,
  autoplayEnabled: true,
  fastForwardToMyTurn: false,
  trickHoldUntilMs: 0,
  heldTrickKey: null,
  seenLastTrickKey: null,
  hasRenderedSnapshot: false,
  snapshot: null,
  selectedPassCards: new Set(),
  seatBotTypeDrafts: {},
  submittedPassCardsByHand: {},
  prePassHandByHand: {},
  receivedPassCardsByHand: {},
  beginHandPendingByHand: {},
  debugViewerRecommendationEnabled: true,
  debugOpponentReasonEnabled: false,
  pacePanelOpen: false,
  debugPanelOpen: false,
};

const SEAT_POSITIONS = ["south", "west", "north", "east"];
const HAND_SUIT_ORDER = { C: 0, D: 1, S: 2, H: 3 };
const RANK_ORDER = {
  "2": 0,
  "3": 1,
  "4": 2,
  "5": 3,
  "6": 4,
  "7": 5,
  "8": 6,
  "9": 7,
  "10": 8,
  J: 9,
  Q: 10,
  K: 11,
  A: 12,
};
const SUIT_META = {
  C: { entity: "&clubs;", className: "clubs" },
  D: { entity: "&diams;", className: "diamonds" },
  H: { entity: "&hearts;", className: "hearts" },
  S: { entity: "&spades;", className: "spades" },
};

const dom = {
  displayName: document.getElementById("displayName"),
  targetScore: document.getElementById("targetScore"),
  seed: document.getElementById("seed"),
  botType: document.getElementById("botType"),
  joinCode: document.getElementById("joinCode"),
  quickSoloBtn: document.getElementById("quickSoloBtn"),
  createBtn: document.getElementById("createBtn"),
  joinBtn: document.getElementById("joinBtn"),
  reconnectBtn: document.getElementById("reconnectBtn"),
  connectionStatus: document.getElementById("connectionStatus"),
  tableCodeValue: document.getElementById("tableCodeValue"),
  viewerSeatValue: document.getElementById("viewerSeatValue"),
  phaseValue: document.getElementById("phaseValue"),
  tableSection: document.getElementById("tableSection"),
  tableSurface: document.getElementById("tableSurface"),
  trickGrid: document.getElementById("trickGrid"),
  lastTrickLine: document.getElementById("lastTrickLine"),
  autoplayBtn: document.getElementById("autoplayBtn"),
  stepBtn: document.getElementById("stepBtn"),
  pacePanelToggle: document.getElementById("pacePanelToggle"),
  pacePanelBody: document.getElementById("pacePanelBody"),
  paceRange: document.getElementById("paceRange"),
  paceValue: document.getElementById("paceValue"),
  fastForwardToggle: document.getElementById("fastForwardToggle"),
  metaLine: document.getElementById("metaLine"),
  infoLine: document.getElementById("infoLine"),
  handGrid: document.getElementById("handGrid"),
  passPanel: document.getElementById("passPanel"),
  passCards: document.getElementById("passCards"),
  passHint: document.getElementById("passHint"),
  submitPassBtn: document.getElementById("submitPassBtn"),
  beginHandBtn: document.getElementById("beginHandBtn"),
  debugPanelToggle: document.getElementById("debugPanelToggle"),
  debugPanelBody: document.getElementById("debugPanelBody"),
  debugViewerToggle: document.getElementById("debugViewerToggle"),
  debugViewerContent: document.getElementById("debugViewerContent"),
  debugOpponentToggle: document.getElementById("debugOpponentToggle"),
  debugOpponentContent: document.getElementById("debugOpponentContent"),
};

function seatPositionForViewer(seat, viewerSeat) {
  const anchorSeat = viewerSeat === null ? 0 : Number(viewerSeat);
  const relative = (Number(seat) - anchorSeat + 4) % 4;
  return SEAT_POSITIONS[relative];
}

function parseCard(cardCode) {
  const normalized = String(cardCode || "").toUpperCase();
  if (normalized.length < 2) {
    return { rank: "?", suit: "?", meta: null };
  }
  const suit = normalized.slice(-1);
  const rank = normalized.slice(0, -1);
  return { rank, suit, meta: SUIT_META[suit] || null };
}

function createCardFace(cardCode, options = {}) {
  const { small = false } = options;
  const parsed = parseCard(cardCode);
  const card = document.createElement("div");
  card.className = "playing-card";
  if (small) {
    card.classList.add("small");
  }
  if (parsed.meta) {
    card.classList.add(`suit-${parsed.meta.className}`);
  }

  const top = document.createElement("span");
  top.className = "corner";
  top.textContent = parsed.rank;

  const center = document.createElement("span");
  center.className = "suit";
  center.innerHTML = parsed.meta ? parsed.meta.entity : "?";

  const bottom = document.createElement("span");
  bottom.className = "corner bottom";
  bottom.textContent = parsed.rank;

  card.append(top, center, bottom);
  card.title = String(cardCode || "");
  return card;
}

function sortCardsForHand(cards) {
  return [...cards].sort((leftCard, rightCard) => {
    const left = parseCard(leftCard);
    const right = parseCard(rightCard);
    const leftSuit = HAND_SUIT_ORDER[left.suit] ?? 99;
    const rightSuit = HAND_SUIT_ORDER[right.suit] ?? 99;
    if (leftSuit !== rightSuit) {
      return leftSuit - rightSuit;
    }
    const leftRank = RANK_ORDER[left.rank] ?? 99;
    const rightRank = RANK_ORDER[right.rank] ?? 99;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    return String(leftCard).localeCompare(String(rightCard));
  });
}

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws`;
}

function globalBotType() {
  if (!dom.botType || !dom.botType.value) {
    return "search_v1";
  }
  return dom.botType.value;
}

function seatDraftBotType(seat) {
  const key = String(seat.seat);
  const draft = appState.seatBotTypeDrafts[key];
  if (draft) {
    return draft;
  }
  if (seat.kind === "bot" && seat.bot_name) {
    return String(seat.bot_name);
  }
  return globalBotType();
}

function setSeatDraftBotType(seat, botType) {
  appState.seatBotTypeDrafts[String(seat)] = String(botType);
}

function handKey(handNumber) {
  return String(Number(handNumber || 0));
}

function passDirectionLabel(direction) {
  const normalized = String(direction || "").toLowerCase();
  if (normalized === "left" || normalized === "right" || normalized === "across" || normalized === "hold") {
    return normalized;
  }
  return "";
}

function formatDebugScore(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return numeric.toFixed(3);
}

function renderPassDecisionLines(decision) {
  const lines = [];
  const payload = decision.payload || {};
  const selected = Array.isArray(payload.selected_cards) ? payload.selected_cards : [];
  if (selected.length === 0 && !Array.isArray(payload.candidates) && payload.label) {
    lines.push(`Reason: ${payload.label}`);
    return lines;
  }
  lines.push(`Selected: ${selected.join(" ") || "-"}`);
  const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
  const top = candidates.slice(0, 5);
  lines.push("Top pass candidates:");
  for (const candidate of top) {
    const score = Array.isArray(candidate.score) ? candidate.score.join(",") : "";
    lines.push(`- ${candidate.card} [${score}]`);
  }
  return lines;
}

function renderHeuristicPlayDecisionLines(payload) {
  const lines = [];
  lines.push(`Mode: ${payload.mode || "-"}`);
  lines.push(`Chosen: ${payload.chosen_card || "-"}`);
  lines.push(`Moon target: ${payload.moon_defense_target ?? "-"}`);
  const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
  const top = candidates.slice(0, 3);
  lines.push("Top play candidates:");
  for (const candidate of top) {
    const tags = Array.isArray(candidate.tags) ? candidate.tags.join(", ") : "";
    lines.push(
      `- ${candidate.card} total=${formatDebugScore(candidate.total_score)} ` +
      `base=${formatDebugScore(candidate.base_score)} rollout=${formatDebugScore(candidate.rollout_score)}`
    );
    if (tags) {
      lines.push(`  tags: ${tags}`);
    }
  }
  return lines;
}

function renderSearchPlayDecisionLines(payload) {
  const lines = [];
  const chosen = payload.chosen && typeof payload.chosen === "object" ? payload.chosen : null;
  const comparison =
    payload.baseline_comparison && typeof payload.baseline_comparison === "object"
      ? payload.baseline_comparison
      : null;
  const baseline =
    comparison && comparison.baseline && typeof comparison.baseline === "object"
      ? comparison.baseline
      : null;

  lines.push(`Mode: ${payload.mode || "-"}`);
  lines.push(`Chosen: ${payload.chosen_card || "-"}`);
  lines.push(`Source: ${payload.selection_source || "-"}`);
  lines.push(`Worlds: ${payload.world_count ?? "-"} / ${payload.requested_world_count ?? "-"}`);
  lines.push(`Candidates: ${payload.evaluated_candidate_count ?? "-"} eval / ${payload.legal_move_count ?? "-"} legal`);
  if (payload.current_trick_size || payload.led_suit) {
    lines.push(`Trick context: size=${payload.current_trick_size ?? 0} led=${payload.led_suit || "-"}`);
  }

  if (chosen) {
    const chosenFacts = [];
    if (chosen.follows_led_suit) {
      chosenFacts.push("follow");
    }
    if (chosen.is_point_card) {
      chosenFacts.push("point");
    }
    if (Number(chosen.trick_points_so_far || 0) > 0) {
      chosenFacts.push(`trick=${chosen.trick_points_so_far}`);
    }
    if (chosen.average_projected_score_delta !== null && chosen.average_projected_score_delta !== undefined) {
      lines.push(
        `Chosen eval: delta=${formatDebugScore(chosen.average_projected_score_delta)} ` +
        `hand=${formatDebugScore(chosen.average_projected_hand_points)} ` +
        `total=${formatDebugScore(chosen.average_projected_total_score)} ` +
        `util=${formatDebugScore(chosen.average_root_utility)}`
      );
    }
    if (chosenFacts.length > 0) {
      lines.push(`Chosen facts: ${chosenFacts.join(", ")}`);
    }
  }

  if (comparison) {
    const agreement = comparison.agrees_with_search ? "agree" : "disagree";
    lines.push(
      `Baseline ${comparison.baseline_bot_name || "heuristic_v3"}: ${baseline?.card || "-"} ` +
      `(${agreement}, rank ${baseline?.selection_rank ?? "-"})`
    );
    lines.push(
      `Vs baseline: delta=${formatDebugScore(comparison.mean_projected_score_delta_advantage)} ` +
      `util=${formatDebugScore(comparison.mean_root_utility_gain)}`
    );
    lines.push(
      `Worlds: win ${comparison.worlds_search_better ?? 0} ` +
      `tie ${comparison.worlds_tied ?? 0} ` +
      `lose ${comparison.worlds_baseline_better ?? 0}`
    );
    lines.push(
      `Range: best +${formatDebugScore(comparison.best_case_root_utility_gain)} ` +
      `worst -${formatDebugScore(comparison.worst_case_root_utility_loss)}`
    );
  }

  if (payload.fallback_message) {
    lines.push(`Fallback: ${payload.fallback_message}`);
  }

  const candidates = Array.isArray(payload.candidates) ? payload.candidates : [];
  if (candidates.length > 0) {
    lines.push("Top search candidates:");
    for (const candidate of candidates.slice(0, 3)) {
      const flags = [];
      if (candidate.selected) {
        flags.push("selected");
      }
      if (
        baseline &&
        baseline.card === candidate.card &&
        baseline.candidate_index === candidate.candidate_index
      ) {
        flags.push("baseline");
      }
      if (candidate.is_point_card) {
        flags.push("point");
      }
      if (candidate.follows_led_suit) {
        flags.push("follow");
      }
      if (Number(candidate.trick_points_so_far || 0) > 0) {
        flags.push(`trick=${candidate.trick_points_so_far}`);
      }
      const suffix = flags.length > 0 ? ` [${flags.join(", ")}]` : "";
      lines.push(
        `- #${candidate.selection_rank} ${candidate.card} ` +
        `delta=${formatDebugScore(candidate.average_projected_score_delta)} ` +
        `hand=${formatDebugScore(candidate.average_projected_hand_points)} ` +
        `util=${formatDebugScore(candidate.average_root_utility)}${suffix}`
      );
    }
  }

  return lines;
}

function renderGenericPlayDecisionLines(payload) {
  const lines = [];
  if (payload.chosen_card || payload.mode) {
    lines.push(`Mode: ${payload.mode || "-"}`);
    lines.push(`Chosen: ${payload.chosen_card || "-"}`);
  }
  if (payload.label) {
    lines.push(`Reason: ${payload.label}`);
  }
  if (lines.length === 0) {
    lines.push("No structured play payload.");
  }
  return lines;
}

function renderPlayDecisionLines(decision) {
  const payload = decision.payload || {};
  if (payload.selection_policy && payload.chosen) {
    return renderSearchPlayDecisionLines(payload);
  }
  if (Object.prototype.hasOwnProperty.call(payload, "moon_defense_target")) {
    return renderHeuristicPlayDecisionLines(payload);
  }
  return renderGenericPlayDecisionLines(payload);
}

function renderViewerRecommendation(snapshot = appState.snapshot) {
  if (!dom.debugViewerContent) {
    return;
  }
  if (!appState.debugViewerRecommendationEnabled) {
    dom.debugViewerContent.textContent = "Enable to inspect recommendation for your own move.";
    return;
  }
  if (!snapshot) {
    dom.debugViewerContent.textContent = "No table snapshot yet.";
    return;
  }
  const recommendation = snapshot.debug_viewer_recommendation;
  const advisoryBot = snapshot.viewer_advisory_bot_name || globalBotType();
  if (!recommendation || typeof recommendation !== "object") {
    dom.debugViewerContent.textContent = `No recommendation payload available. Advisory bot: ${advisoryBot}.`;
    return;
  }

  const status = String(recommendation.status || "idle");
  if (status !== "ok") {
    const message = recommendation.message ? String(recommendation.message) : "No recommendation available.";
    dom.debugViewerContent.textContent = `Advisory bot: ${advisoryBot}\nStatus: ${status}\n${message}`;
    return;
  }

  const lines = [
    `Seat P${recommendation.seat} (${recommendation.bot_name})`,
    `Kind ${recommendation.decision_kind}  Hand ${recommendation.hand_number}  Trick ${recommendation.trick_number}`,
  ];
  if (recommendation.decision_kind === "pass") {
    lines.push(...renderPassDecisionLines(recommendation));
  } else if (recommendation.decision_kind === "play") {
    lines.push(...renderPlayDecisionLines(recommendation));
  } else {
    lines.push("Unsupported recommendation payload.");
  }
  dom.debugViewerContent.textContent = lines.join("\n");
}

function renderOpponentReason(snapshot = appState.snapshot) {
  if (!dom.debugOpponentContent) {
    return;
  }
  if (!appState.debugOpponentReasonEnabled) {
    dom.debugOpponentContent.textContent = "Enable to inspect the latest bot decision.";
    return;
  }
  if (!snapshot || !snapshot.debug_last_bot_decision) {
    dom.debugOpponentContent.textContent = "No bot decision captured yet.";
    return;
  }

  const decision = snapshot.debug_last_bot_decision;
  const lines = [
    `Seat P${decision.seat} (${decision.bot_name})`,
    `Kind ${decision.decision_kind}  Hand ${decision.hand_number}  Trick ${decision.trick_number}`,
  ];
  if (decision.decision_kind === "pass") {
    lines.push(...renderPassDecisionLines(decision));
  } else if (decision.decision_kind === "play") {
    lines.push(...renderPlayDecisionLines(decision));
  } else {
    lines.push("Unsupported decision payload.");
  }
  dom.debugOpponentContent.textContent = lines.join("\n");
}

function renderDebugPanels(snapshot = appState.snapshot) {
  renderViewerRecommendation(snapshot);
  renderOpponentReason(snapshot);
}

function updateCollapsiblePanels() {
  if (dom.pacePanelBody && dom.pacePanelToggle) {
    dom.pacePanelBody.classList.toggle("hidden", !appState.pacePanelOpen);
    dom.pacePanelToggle.setAttribute("aria-expanded", appState.pacePanelOpen ? "true" : "false");
    dom.pacePanelToggle.textContent = appState.pacePanelOpen ? "Hide" : "Show";
    dom.pacePanelToggle.title = appState.pacePanelOpen ? "Hide Pace controls" : "Show Pace controls";
  }
  if (dom.debugPanelBody && dom.debugPanelToggle) {
    dom.debugPanelBody.classList.toggle("hidden", !appState.debugPanelOpen);
    dom.debugPanelToggle.setAttribute("aria-expanded", appState.debugPanelOpen ? "true" : "false");
    dom.debugPanelToggle.textContent = appState.debugPanelOpen ? "Hide" : "Show";
    dom.debugPanelToggle.title = appState.debugPanelOpen ? "Hide Bot Debug" : "Show Bot Debug";
  }
}

function setPacePanelOpen(isOpen) {
  appState.pacePanelOpen = Boolean(isOpen);
  updateCollapsiblePanels();
}

function setDebugPanelOpen(isOpen) {
  appState.debugPanelOpen = Boolean(isOpen);
  updateCollapsiblePanels();
}

function togglePacePanel() {
  setPacePanelOpen(!appState.pacePanelOpen);
}

function toggleDebugPanel() {
  setDebugPanelOpen(!appState.debugPanelOpen);
}

function applySnapshot(snapshot) {
  const previous = appState.snapshot;
  maybeCaptureReceivedPassCards(previous, snapshot);
  appState.snapshot = snapshot;
  render();
}

function maybeCaptureReceivedPassCards(previous, nextSnapshot) {
  if (!previous || !nextSnapshot) {
    return;
  }
  if (previous.phase !== "passing" || nextSnapshot.phase !== "playing") {
    return;
  }
  if (Number(nextSnapshot.trick_number || 0) !== 0) {
    return;
  }
  if (nextSnapshot.viewer_seat === null) {
    return;
  }

  const key = handKey(nextSnapshot.hand_number);
  const submitted = appState.submittedPassCardsByHand[key] || [];
  if (submitted.length === 0) {
    appState.receivedPassCardsByHand[key] = [];
    appState.beginHandPendingByHand[key] = false;
    return;
  }

  const prePassHand = appState.prePassHandByHand[key] || previous.viewer_hand || [];
  const submittedSet = new Set(submitted);
  const keptCards = new Set(prePassHand.filter((card) => !submittedSet.has(card)));
  const currentHand = nextSnapshot.viewer_hand || [];
  appState.receivedPassCardsByHand[key] = currentHand.filter((card) => !keptCards.has(card));
  appState.beginHandPendingByHand[key] = appState.receivedPassCardsByHand[key].length > 0;
}

function receivedPassCards(snapshot = appState.snapshot) {
  if (!snapshot) {
    return [];
  }
  if (snapshot.phase !== "playing" || Number(snapshot.trick_number || 0) !== 0) {
    return [];
  }
  return appState.receivedPassCardsByHand[handKey(snapshot.hand_number)] || [];
}

function isBeginHandPending(snapshot = appState.snapshot) {
  if (!snapshot) {
    return false;
  }
  if (snapshot.phase !== "playing") {
    return false;
  }
  if (snapshot.viewer_seat === null) {
    return false;
  }
  if (Number(snapshot.trick_number || 0) !== 0) {
    return false;
  }
  if ((snapshot.current_trick || []).length !== 0) {
    return false;
  }
  if (receivedPassCards(snapshot).length === 0) {
    return false;
  }
  return Boolean(appState.beginHandPendingByHand[handKey(snapshot.hand_number)]);
}

function setConnectionStatus(label, connected) {
  dom.connectionStatus.textContent = label;
  dom.connectionStatus.classList.toggle("muted", !connected);
}

function setInfo(text) {
  dom.infoLine.textContent = text;
}

function saveSession() {
  const payload = {
    tableCode: appState.tableCode,
    playerSecret: appState.playerSecret,
    displayName: appState.displayName,
  };
  window.localStorage.setItem("hearts_ai_session", JSON.stringify(payload));
}

function clearAdvanceTimer() {
  if (!appState.advanceTimer) {
    return;
  }
  window.clearTimeout(appState.advanceTimer);
  appState.advanceTimer = null;
}

function clearTrickHoldTimer() {
  if (!appState.trickHoldTimer) {
    return;
  }
  window.clearTimeout(appState.trickHoldTimer);
  appState.trickHoldTimer = null;
}

function lastTrickKey(snapshot = appState.snapshot) {
  if (!snapshot || !snapshot.last_trick) {
    return null;
  }
  return `${snapshot.hand_number}:${snapshot.last_trick.trick_seq}`;
}

function isTrickHoldActive(snapshot = appState.snapshot) {
  const key = lastTrickKey(snapshot);
  if (!key) {
    return false;
  }
  if (appState.heldTrickKey !== key) {
    return false;
  }
  return Date.now() < appState.trickHoldUntilMs;
}

function activateTrickHold(trickKey) {
  appState.heldTrickKey = trickKey;
  appState.trickHoldUntilMs = Date.now() + TRICK_HOLD_MS;
  clearTrickHoldTimer();
  appState.trickHoldTimer = window.setTimeout(() => {
    appState.trickHoldUntilMs = 0;
    appState.heldTrickKey = null;
    appState.trickHoldTimer = null;
    render();
  }, TRICK_HOLD_MS);
}

function maybeActivateTrickHold(snapshot) {
  const trickKey = lastTrickKey(snapshot);
  if (!trickKey) {
    return;
  }
  if (!appState.hasRenderedSnapshot) {
    appState.seenLastTrickKey = trickKey;
    return;
  }
  if (trickKey !== appState.seenLastTrickKey) {
    activateTrickHold(trickKey);
    appState.seenLastTrickKey = trickKey;
  }
}

function updatePaceControls(snapshot = appState.snapshot) {
  const canControl = canControlPace(snapshot);
  dom.autoplayBtn.disabled = !canControl;
  dom.stepBtn.disabled = !canControl || appState.advanceInFlight;
  dom.paceRange.disabled = !canControl;
  dom.fastForwardToggle.disabled = !canControl;

  const autoplayTitle = appState.autoplayEnabled ? "Pause autoplay (Space)" : "Resume autoplay (Space)";
  const autoplayIcon = dom.autoplayBtn.querySelector(".icon-glyph");
  if (autoplayIcon) {
    autoplayIcon.textContent = appState.autoplayEnabled ? "❚❚" : "▶";
  }
  dom.autoplayBtn.setAttribute("aria-label", autoplayTitle);
  dom.autoplayBtn.setAttribute("aria-pressed", appState.autoplayEnabled ? "true" : "false");
  dom.autoplayBtn.title = autoplayTitle;
  dom.stepBtn.setAttribute("aria-label", "Advance one action (N)");
  dom.stepBtn.title = "Advance one action (N)";
  dom.paceRange.value = String(appState.paceMs);
  dom.fastForwardToggle.checked = appState.fastForwardToMyTurn;
  dom.paceValue.textContent = `${appState.paceMs}ms`;
}

function canControlPace(snapshot) {
  return Boolean(snapshot && snapshot.viewer_can_control_pace);
}

function setAutoplayEnabled(enabled) {
  appState.autoplayEnabled = Boolean(enabled);
  updatePaceControls();
  scheduleAutoAdvance();
}

function toggleAutoplay() {
  if (!dom.autoplayBtn || dom.autoplayBtn.disabled) {
    return;
  }
  setAutoplayEnabled(!appState.autoplayEnabled);
}

function requestStepAdvance() {
  if (!dom.stepBtn || dom.stepBtn.disabled) {
    return;
  }
  void advanceOneAction();
}

function isEditableKeyTarget(target) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  return target.closest("input, textarea, select, button, [contenteditable='true']") !== null;
}

function handleGlobalKeydown(event) {
  if (event.defaultPrevented || event.repeat || event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }
  if (isEditableKeyTarget(event.target)) {
    return;
  }

  if (event.code === "Space") {
    if (dom.autoplayBtn && !dom.autoplayBtn.disabled) {
      event.preventDefault();
      toggleAutoplay();
    }
    return;
  }

  if (typeof event.key === "string" && event.key.toLowerCase() === "n") {
    if (dom.stepBtn && !dom.stepBtn.disabled) {
      event.preventDefault();
      requestStepAdvance();
    }
  }
}

function shouldAutoAdvance(snapshot) {
  if (!snapshot || !appState.tableCode || !appState.playerSecret) {
    return false;
  }
  if (!appState.autoplayEnabled) {
    return false;
  }
  if (!canControlPace(snapshot)) {
    return false;
  }
  if (isTrickHoldActive(snapshot)) {
    return false;
  }
  if (isBeginHandPending(snapshot)) {
    return false;
  }

  if (snapshot.phase === "hand_scoring") {
    return true;
  }

  if (snapshot.phase === "passing") {
    if (snapshot.viewer_seat === null) {
      return false;
    }
    const viewerKey = String(snapshot.viewer_seat);
    return Boolean(snapshot.pass_submissions && snapshot.pass_submissions[viewerKey]);
  }

  if (snapshot.phase === "playing") {
    if (snapshot.turn === null) {
      return false;
    }
    if (snapshot.viewer_seat !== null && snapshot.turn === snapshot.viewer_seat) {
      return (snapshot.viewer_legal_moves || []).length === 0;
    }
    return true;
  }

  return false;
}

async function advanceOneAction() {
  if (appState.advanceInFlight || !appState.tableCode || !appState.playerSecret) {
    return;
  }
  appState.advanceInFlight = true;
  try {
    const response = await apiRequest(`/tables/${appState.tableCode}/advance`, "POST", {
      player_secret: appState.playerSecret,
    });
    if (response && response.snapshot) {
      applySnapshot(response.snapshot);
    }
  } catch (error) {
    setInfo(error.message);
  } finally {
    appState.advanceInFlight = false;
    updatePaceControls();
    scheduleAutoAdvance();
  }
}

function scheduleAutoAdvance(snapshot = appState.snapshot) {
  clearAdvanceTimer();
  if (appState.advanceInFlight) {
    return;
  }
  if (!shouldAutoAdvance(snapshot)) {
    return;
  }
  let delayMs = appState.paceMs;
  if (snapshot && snapshot.phase === "passing") {
    delayMs = Math.min(delayMs, PASS_AUTOPLAY_DELAY_MS);
  }
  if (
    appState.fastForwardToMyTurn &&
    snapshot &&
    snapshot.phase === "playing" &&
    snapshot.viewer_seat !== null &&
    snapshot.turn !== snapshot.viewer_seat
  ) {
    delayMs = Math.min(FAST_FORWARD_PACE_MS, appState.paceMs);
  }
  appState.advanceTimer = window.setTimeout(() => {
    void advanceOneAction();
  }, delayMs);
}

function loadSession() {
  const raw = window.localStorage.getItem("hearts_ai_session");
  if (!raw) {
    return;
  }
  try {
    const decoded = JSON.parse(raw);
    appState.tableCode = typeof decoded.tableCode === "string" ? decoded.tableCode : null;
    appState.playerSecret = typeof decoded.playerSecret === "string" ? decoded.playerSecret : null;
    appState.displayName = typeof decoded.displayName === "string" ? decoded.displayName : "";
  } catch (_) {
    window.localStorage.removeItem("hearts_ai_session");
  }
}

async function apiRequest(path, method, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await window.fetch(path, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch (_) {
    payload = null;
  }

  if (!response.ok) {
    const message = payload && payload.detail ? payload.detail : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

function readCreateOptions() {
  const displayName = dom.displayName.value.trim();
  if (!displayName) {
    setInfo("Enter a display name first.");
    return null;
  }

  const targetScore = Number(dom.targetScore.value);
  const seedRaw = dom.seed.value.trim();
  const payload = {
    display_name: displayName,
    target_score: Number.isFinite(targetScore) ? targetScore : 50,
  };
  if (seedRaw) {
    const seed = Number(seedRaw);
    if (!Number.isFinite(seed)) {
      setInfo("Seed must be a valid number.");
      return null;
    }
    payload.seed = seed;
  }
  return { displayName, payload };
}

function applyCreatedTableSession(created, displayName) {
  appState.tableCode = created.table_code;
  appState.playerSecret = created.player_secret;
  appState.displayName = displayName;
  dom.joinCode.value = created.table_code;
  appState.selectedPassCards.clear();
  appState.seatBotTypeDrafts = {};
  appState.submittedPassCardsByHand = {};
  appState.prePassHandByHand = {};
  appState.receivedPassCardsByHand = {};
  appState.beginHandPendingByHand = {};
  saveSession();
}

async function createTable() {
  const options = readCreateOptions();
  if (!options) {
    return;
  }

  try {
    const created = await apiRequest("/tables", "POST", options.payload);
    applyCreatedTableSession(created, options.displayName);
    await fetchSnapshot();
    await setViewerAdvisoryBotPreference(globalBotType());
    connectWebSocket();
  } catch (error) {
    setInfo(error.message);
  }
}

async function quickStartSolo() {
  const options = readCreateOptions();
  if (!options) {
    return;
  }

  try {
    const created = await apiRequest("/tables", "POST", options.payload);
    applyCreatedTableSession(created, options.displayName);

    await apiRequest(`/tables/${appState.tableCode}/seats/0`, "POST", {
      player_secret: appState.playerSecret,
    });
    const botName = globalBotType();
    for (const seat of [1, 2, 3]) {
      await apiRequest(`/tables/${appState.tableCode}/bots/${seat}`, "POST", {
        bot_name: botName,
      });
    }

    await fetchSnapshot();
    await setViewerAdvisoryBotPreference(globalBotType());
    connectWebSocket();
  } catch (error) {
    setInfo(error.message);
  }
}

async function joinTable() {
  const tableCode = dom.joinCode.value.trim().toUpperCase();
  const displayName = dom.displayName.value.trim();
  if (!tableCode) {
    setInfo("Enter a table code to join.");
    return;
  }
  if (!displayName) {
    setInfo("Enter a display name first.");
    return;
  }

  try {
    const joined = await apiRequest(`/tables/${tableCode}/join`, "POST", { display_name: displayName });
    appState.tableCode = joined.table_code;
    appState.playerSecret = joined.player_secret;
    appState.displayName = displayName;
    appState.selectedPassCards.clear();
    appState.seatBotTypeDrafts = {};
    appState.submittedPassCardsByHand = {};
    appState.prePassHandByHand = {};
    appState.receivedPassCardsByHand = {};
    appState.beginHandPendingByHand = {};
    saveSession();
    await fetchSnapshot();
    await setViewerAdvisoryBotPreference(globalBotType());
    connectWebSocket();
  } catch (error) {
    setInfo(error.message);
  }
}

async function reconnectSession() {
  if (!appState.tableCode || !appState.playerSecret) {
    setInfo("No previous session found.");
    return;
  }

  try {
    await fetchSnapshot();
    await setViewerAdvisoryBotPreference(globalBotType());
    connectWebSocket();
  } catch (error) {
    setInfo(error.message);
  }
}

async function fetchSnapshot() {
  if (!appState.tableCode) {
    return;
  }
  const secretQuery = appState.playerSecret
    ? `?player_secret=${encodeURIComponent(appState.playerSecret)}`
    : "";
  const snapshot = await apiRequest(`/tables/${appState.tableCode}${secretQuery}`, "GET");
  applySnapshot(snapshot);
}

function connectWebSocket() {
  if (!appState.tableCode) {
    return;
  }
  if (appState.ws && appState.ws.readyState === WebSocket.OPEN) {
    return;
  }
  if (appState.ws && appState.ws.readyState === WebSocket.CONNECTING) {
    return;
  }

  if (appState.ws) {
    appState.ws.close();
  }

  const socket = new WebSocket(wsUrl());
  appState.ws = socket;
  setConnectionStatus("connecting", false);

  socket.addEventListener("open", () => {
    setConnectionStatus("online", true);
    const message = {
      schema_version: SCHEMA_VERSION,
      type: "join_table",
      table_code: appState.tableCode,
      display_name: appState.displayName || "Player",
    };
    if (appState.playerSecret) {
      message.player_secret = appState.playerSecret;
    }
    socket.send(JSON.stringify(message));
  });

  socket.addEventListener("message", (event) => {
    let message = null;
    try {
      message = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    if (!message || typeof message !== "object") {
      return;
    }

    if (message.type === "table_joined") {
      if (typeof message.player_secret === "string") {
        appState.playerSecret = message.player_secret;
        saveSession();
      }
      return;
    }

    if (message.type === "state_snapshot") {
      applySnapshot(message.payload || null);
      return;
    }

    if (message.type === "error") {
      setInfo(message.message || "Server error.");
      return;
    }
  });

  socket.addEventListener("close", () => {
    setConnectionStatus("offline", false);
    clearAdvanceTimer();
    clearTrickHoldTimer();
    appState.advanceInFlight = false;
    if (!appState.tableCode) {
      return;
    }
    if (appState.reconnectTimer) {
      window.clearTimeout(appState.reconnectTimer);
    }
    appState.reconnectTimer = window.setTimeout(() => {
      connectWebSocket();
    }, RECONNECT_DELAY_MS);
  });
}

async function claimSeat(seat) {
  if (!appState.tableCode || !appState.playerSecret) {
    setInfo("Join a table first.");
    return;
  }
  try {
    await apiRequest(`/tables/${appState.tableCode}/seats/${seat}`, "POST", {
      player_secret: appState.playerSecret,
    });
    await fetchSnapshot();
  } catch (error) {
    setInfo(error.message);
  }
}

async function addBot(seat, botName = null) {
  if (!appState.tableCode) {
    setInfo("Create or join a table first.");
    return;
  }
  try {
    const nextBot = botName || globalBotType();
    await apiRequest(`/tables/${appState.tableCode}/bots/${seat}`, "POST", {
      bot_name: nextBot,
    });
    setSeatDraftBotType(seat, nextBot);
    await fetchSnapshot();
  } catch (error) {
    setInfo(error.message);
  }
}

async function setViewerAdvisoryBotPreference(botName = null) {
  if (!appState.tableCode || !appState.playerSecret) {
    return;
  }
  const nextBot = botName || globalBotType();
  await apiRequest(`/tables/${appState.tableCode}/viewer-advisory-bot`, "POST", {
    player_secret: appState.playerSecret,
    bot_name: nextBot,
  });
}

async function submitPass() {
  if (!appState.tableCode || !appState.playerSecret || !appState.snapshot) {
    return;
  }
  const passCount = Number(appState.snapshot.pass_count || 3);
  if (appState.selectedPassCards.size !== passCount) {
    setInfo(`Select exactly ${passCount} cards to pass.`);
    return;
  }
  try {
    const key = handKey(appState.snapshot.hand_number);
    appState.submittedPassCardsByHand[key] = Array.from(appState.selectedPassCards);
    appState.prePassHandByHand[key] = [...(appState.snapshot.viewer_hand || [])];

    await apiRequest(`/tables/${appState.tableCode}/pass`, "POST", {
      player_secret: appState.playerSecret,
      cards: Array.from(appState.selectedPassCards),
    });
    appState.selectedPassCards.clear();
    await fetchSnapshot();
  } catch (error) {
    setInfo(error.message);
  }
}

async function playCard(cardCode) {
  if (!appState.tableCode || !appState.playerSecret) {
    return;
  }
  try {
    await apiRequest(`/tables/${appState.tableCode}/play`, "POST", {
      player_secret: appState.playerSecret,
      card: cardCode,
    });
    await fetchSnapshot();
  } catch (error) {
    setInfo(error.message);
  }
}

function renderSeat(snapshot, seat, seatPosition) {
  const seatBox = document.createElement("div");
  seatBox.className = `table-seat pos-${seatPosition}`;
  const seatKey = String(seat.seat);
  const cumulativeScore = Number(snapshot.scores[seatKey] || 0);
  const currentHandPoints = Number(snapshot.seat_hand_points[seatKey] || 0);
  const liveTotalScore =
    snapshot.phase === "playing" ? cumulativeScore + currentHandPoints : cumulativeScore;
  if (snapshot.viewer_seat === seat.seat) {
    seatBox.classList.add("you");
  }
  if (seat.kind === "bot") {
    seatBox.classList.add("bot");
  }
  if (snapshot.phase === "playing" && snapshot.turn === seat.seat) {
    seatBox.classList.add("active");
  }
  if (seat.kind === "open") {
    seatBox.classList.add("open");
  }

  const head = document.createElement("div");
  head.className = "seat-head";
  const seatId = document.createElement("span");
  seatId.className = "seat-id";
  seatId.textContent = `P${seat.seat}`;

  const seatStatus = document.createElement("div");
  seatStatus.className = "seat-status";

  const seatKind = document.createElement("span");
  seatKind.className = "seat-kind";
  seatKind.textContent = seat.kind;
  seatStatus.append(seatKind);
  head.append(seatId, seatStatus);

  const nameRow = document.createElement("div");
  nameRow.className = "seat-name-row";

  const name = document.createElement("div");
  name.className = "seat-name";
  if (seat.kind === "bot") {
    const botName = seat.bot_name ? String(seat.bot_name) : "random";
    name.textContent = `Bot (${botName})`;
  } else {
    name.textContent = seat.display_name || (seat.kind === "open" ? "Open seat" : "Bot");
  }

  const handValue = document.createElement("span");
  handValue.className = "seat-hand-big";
  handValue.textContent = String(snapshot.seat_hand_points[seatKey] || 0);

  nameRow.append(name, handValue);

  const metrics = document.createElement("div");
  metrics.className = "seat-metrics";

  const totalMetric = document.createElement("span");
  totalMetric.className = "seat-metric seat-metric-total";
  totalMetric.textContent = `Total ${liveTotalScore}`;
  metrics.append(totalMetric);

  seatBox.append(head, nameRow, metrics);

  const canConfigureBots = snapshot.phase === "lobby" && Boolean(appState.playerSecret);

  if (seat.kind === "open" && canConfigureBots) {
    const actions = document.createElement("div");
    actions.className = "seat-actions";

    const claimBtn = document.createElement("button");
    claimBtn.className = "ghost";
    claimBtn.textContent = "Claim";
    claimBtn.addEventListener("click", () => claimSeat(seat.seat));
    actions.appendChild(claimBtn);

    const botBtn = document.createElement("button");
    botBtn.className = "ghost";
    botBtn.textContent = "Add bot";
    const botSelect = document.createElement("select");
    botSelect.className = "ghost";
    const openDefault = seatDraftBotType(seat);
    for (const botName of BOT_OPTIONS) {
      const option = document.createElement("option");
      option.value = botName;
      option.textContent = botName;
      if (botName === openDefault) {
        option.selected = true;
      }
      botSelect.appendChild(option);
    }
    botSelect.addEventListener("change", () => {
      setSeatDraftBotType(seat.seat, botSelect.value);
    });
    botBtn.addEventListener("click", () => addBot(seat.seat, botSelect.value));
    actions.appendChild(botSelect);
    actions.appendChild(botBtn);

    seatBox.appendChild(actions);
  }

  if (seat.kind === "bot" && canConfigureBots) {
    const actions = document.createElement("div");
    actions.className = "seat-actions";

    const botSelect = document.createElement("select");
    botSelect.className = "ghost";
    const current = seatDraftBotType(seat);
    for (const botName of BOT_OPTIONS) {
      const option = document.createElement("option");
      option.value = botName;
      option.textContent = botName;
      if (botName === current) {
        option.selected = true;
      }
      botSelect.appendChild(option);
    }
    botSelect.addEventListener("change", () => {
      setSeatDraftBotType(seat.seat, botSelect.value);
    });

    const updateBtn = document.createElement("button");
    updateBtn.className = "ghost";
    updateBtn.textContent = "Set bot";
    updateBtn.addEventListener("click", () => addBot(seat.seat, botSelect.value));

    actions.append(botSelect, updateBtn);
    seatBox.appendChild(actions);
  }

  return seatBox;
}

function renderTrick(snapshot, seatPositionById) {
  dom.trickGrid.innerHTML = "";
  dom.trickGrid.classList.remove("resolved");

  let displayedTrick = snapshot.current_trick || [];
  let isResolvedDisplay = false;
  if (
    displayedTrick.length === 0 &&
    snapshot.last_trick &&
    isTrickHoldActive(snapshot)
  ) {
    displayedTrick = snapshot.last_trick.cards || [];
    isResolvedDisplay = true;
    dom.trickGrid.classList.add("resolved");
  }

  for (const seat of snapshot.seats) {
    const slot = document.createElement("div");
    slot.className = `trick-slot pos-${seatPositionById[seat.seat]}`;

    const label = document.createElement("span");
    label.className = "trick-label";
    label.textContent = `P${seat.seat}`;
    slot.appendChild(label);

    const play = displayedTrick.find((entry) => entry.player_id === seat.seat);
    if (play) {
      slot.appendChild(createCardFace(play.card, { small: true }));
    }

    dom.trickGrid.appendChild(slot);
  }

  if (displayedTrick.length === 0 || isResolvedDisplay) {
    return;
  }
}

function renderLastTrick(snapshot) {
  if (!snapshot.last_trick) {
    dom.lastTrickLine.textContent = "No completed trick yet.";
    return;
  }
  const points = Number(snapshot.last_trick.points || 0);
  const winner = Number(snapshot.last_trick.winner);
  const pointWord = points === 1 ? "point" : "points";
  dom.lastTrickLine.textContent =
    `Last trick: P${winner} took ${points} ${pointWord} (T${snapshot.last_trick.trick_seq}).`;
}

function renderTable(snapshot) {
  for (const child of Array.from(dom.tableSurface.children)) {
    if (child !== dom.trickGrid) {
      child.remove();
    }
  }

  const seatPositionById = {};
  for (const seat of snapshot.seats) {
    const position = seatPositionForViewer(seat.seat, snapshot.viewer_seat);
    seatPositionById[seat.seat] = position;
    dom.tableSurface.appendChild(renderSeat(snapshot, seat, position));
  }

  renderTrick(snapshot, seatPositionById);
  renderLastTrick(snapshot);
}

function togglePassCard(cardCode, passCount) {
  if (appState.selectedPassCards.has(cardCode)) {
    appState.selectedPassCards.delete(cardCode);
  } else if (appState.selectedPassCards.size < passCount) {
    appState.selectedPassCards.add(cardCode);
  }
  render();
}

function renderPassPanel(snapshot) {
  const viewerSeat = snapshot.viewer_seat;
  const passCount = Number(snapshot.pass_count || 3);
  const passDirection = passDirectionLabel(snapshot.pass_direction);
  const viewerKey = viewerSeat === null ? null : String(viewerSeat);
  const alreadySubmitted =
    viewerKey !== null && snapshot.pass_submissions && snapshot.pass_submissions[viewerKey] === true;

  const isVisible = snapshot.phase === "passing" && viewerSeat !== null;
  dom.passPanel.classList.toggle("hidden", !isVisible);

  if (!isVisible) {
    return;
  }

  dom.passCards.innerHTML = "";
  if (alreadySubmitted) {
    dom.passHint.textContent = passDirection
      ? `Pass submitted (${passDirection}). Waiting for other players.`
      : "Pass submitted. Waiting for other players.";
  } else {
    dom.passHint.textContent = passDirection
      ? `Select ${passCount} cards to pass ${passDirection}.`
      : `Select ${passCount} cards to pass.`;
  }

  const orderedHand = sortCardsForHand(snapshot.viewer_hand || []);
  for (const card of orderedHand) {
    const button = document.createElement("button");
    button.className = "card-btn";
    button.appendChild(createCardFace(card));
    button.title = `Pass ${card}`;
    if (appState.selectedPassCards.has(card)) {
      button.classList.add("selected");
    }
    if (alreadySubmitted) {
      button.disabled = true;
    } else {
      button.addEventListener("click", () => togglePassCard(card, passCount));
    }
    dom.passCards.appendChild(button);
  }

  dom.submitPassBtn.disabled = alreadySubmitted || appState.selectedPassCards.size !== passCount;
}

function renderHand(snapshot) {
  dom.handGrid.innerHTML = "";
  const legal = new Set(snapshot.viewer_legal_moves || []);
  const received = new Set(receivedPassCards(snapshot));
  const beginPending = isBeginHandPending(snapshot);
  const canPlay = !beginPending && snapshot.phase === "playing" && snapshot.turn === snapshot.viewer_seat;
  const orderedHand = sortCardsForHand(snapshot.viewer_hand || []);
  for (const card of orderedHand) {
    const button = document.createElement("button");
    button.className = "card-btn";
    button.appendChild(createCardFace(card));
    button.title = `Play ${card}`;
    if (received.has(card)) {
      button.classList.add("received");
      button.title = `New from pass: ${card}`;
    }
    if (!beginPending && legal.has(card)) {
      button.classList.add("legal");
    }

    if (canPlay && legal.has(card)) {
      button.classList.add("play");
      button.addEventListener("click", () => playCard(card));
    } else if (!beginPending) {
      button.disabled = true;
    } else {
      button.classList.add("review-locked");
    }

    dom.handGrid.appendChild(button);
  }
}

function renderBeginHandButton(snapshot) {
  const visible = isBeginHandPending(snapshot);
  dom.beginHandBtn.classList.toggle("hidden", !visible);
  dom.beginHandBtn.disabled = !visible;
}

function beginHand() {
  const snapshot = appState.snapshot;
  if (!isBeginHandPending(snapshot)) {
    return;
  }
  appState.beginHandPendingByHand[handKey(snapshot.hand_number)] = false;
  render();
}

function render(snapshot = appState.snapshot) {
  dom.tableCodeValue.textContent = appState.tableCode || "-";
  if (!snapshot) {
    dom.phaseValue.textContent = "-";
    dom.viewerSeatValue.textContent = "spectator";
    dom.tableSection.classList.add("hidden");
    clearAdvanceTimer();
    clearTrickHoldTimer();
    dom.beginHandBtn.classList.add("hidden");
    appState.hasRenderedSnapshot = false;
    updatePaceControls(null);
    renderDebugPanels(null);
    updateCollapsiblePanels();
    return;
  }

  if (!snapshot.seat_hand_points) {
    snapshot.seat_hand_points = { "0": 0, "1": 0, "2": 0, "3": 0 };
  }
  if (!("last_trick" in snapshot)) {
    snapshot.last_trick = null;
  }
  maybeActivateTrickHold(snapshot);

  dom.tableSection.classList.remove("hidden");
  dom.phaseValue.textContent = snapshot.phase;
  dom.viewerSeatValue.textContent =
    snapshot.viewer_seat === null ? "spectator" : `P${snapshot.viewer_seat}`;
  dom.metaLine.textContent =
    `Hand ${snapshot.hand_number}  Trick ${snapshot.trick_number}  ` +
    `Pass ${snapshot.pass_direction}  HeartsBroken ${snapshot.hearts_broken ? "yes" : "no"}  ` +
    `Target ${snapshot.target_score}`;

  if (snapshot.phase === "lobby") {
    setInfo("Fill all four seats with humans or bots to begin.");
    appState.selectedPassCards.clear();
  } else if (snapshot.phase === "passing") {
    if (snapshot.viewer_seat === null) {
      setInfo("Spectating pass phase.");
    } else {
      const me = String(snapshot.viewer_seat);
      if (snapshot.pass_submissions && snapshot.pass_submissions[me]) {
        setInfo("Pass submitted. Waiting for the table.");
      } else {
        setInfo("Select cards and submit pass.");
      }
    }
  } else if (snapshot.phase === "playing") {
    const receivedCards = receivedPassCards(snapshot);
    let baseInfo = "Waiting for next turn.";
    if (snapshot.viewer_seat !== null && snapshot.turn === snapshot.viewer_seat) {
      baseInfo = "Your turn. Play a legal card.";
    } else if (snapshot.turn !== null) {
      baseInfo = `Waiting on P${snapshot.turn}.`;
    }
    if (isBeginHandPending(snapshot)) {
      setInfo(`Review new cards from pass, then click Begin Hand. New: ${receivedCards.join(" ")}`);
    } else if (receivedCards.length > 0) {
      setInfo(`${baseInfo} New from pass: ${receivedCards.join(" ")}`);
    } else {
      setInfo(baseInfo);
    }
  } else if (snapshot.phase === "game_over") {
    setInfo("Game over. Create another table to play again.");
  }

  renderTable(snapshot);
  renderPassPanel(snapshot);
  renderHand(snapshot);
  renderBeginHandButton(snapshot);
  renderDebugPanels(snapshot);
  updatePaceControls(snapshot);
  updateCollapsiblePanels();
  appState.hasRenderedSnapshot = true;
  scheduleAutoAdvance(snapshot);
}

function wireEvents() {
  dom.quickSoloBtn.addEventListener("click", quickStartSolo);
  dom.createBtn.addEventListener("click", createTable);
  dom.joinBtn.addEventListener("click", joinTable);
  dom.reconnectBtn.addEventListener("click", reconnectSession);
  dom.submitPassBtn.addEventListener("click", submitPass);
  dom.beginHandBtn.addEventListener("click", beginHand);
  dom.autoplayBtn.addEventListener("click", toggleAutoplay);
  dom.stepBtn.addEventListener("click", requestStepAdvance);
  if (dom.pacePanelToggle) {
    dom.pacePanelToggle.addEventListener("click", togglePacePanel);
  }
  if (dom.debugPanelToggle) {
    dom.debugPanelToggle.addEventListener("click", toggleDebugPanel);
  }
  dom.paceRange.addEventListener("input", () => {
    const parsed = Number(dom.paceRange.value);
    if (!Number.isFinite(parsed)) {
      return;
    }
    const next = Math.max(200, Math.min(2000, Math.round(parsed)));
    appState.paceMs = next;
    updatePaceControls();
    scheduleAutoAdvance();
  });
  dom.fastForwardToggle.addEventListener("change", () => {
    appState.fastForwardToMyTurn = dom.fastForwardToggle.checked;
    updatePaceControls();
    scheduleAutoAdvance();
  });
  if (dom.botType) {
    dom.botType.addEventListener("change", () => {
      if (!appState.tableCode || !appState.playerSecret) {
        return;
      }
      void setViewerAdvisoryBotPreference(globalBotType()).catch((error) => {
        setInfo(error.message);
      });
    });
  }
  if (dom.debugViewerToggle) {
    dom.debugViewerToggle.addEventListener("change", () => {
      appState.debugViewerRecommendationEnabled = dom.debugViewerToggle.checked;
      renderDebugPanels();
    });
  }
  if (dom.debugOpponentToggle) {
    dom.debugOpponentToggle.addEventListener("change", () => {
      appState.debugOpponentReasonEnabled = dom.debugOpponentToggle.checked;
      renderDebugPanels();
    });
  }
  document.addEventListener("keydown", handleGlobalKeydown);
}

function boot() {
  loadSession();
  if (appState.displayName) {
    dom.displayName.value = appState.displayName;
  }
  if (appState.tableCode) {
    dom.joinCode.value = appState.tableCode;
    dom.tableCodeValue.textContent = appState.tableCode;
  }
  if (dom.debugViewerToggle) {
    dom.debugViewerToggle.checked = appState.debugViewerRecommendationEnabled;
  }
  if (dom.debugOpponentToggle) {
    dom.debugOpponentToggle.checked = appState.debugOpponentReasonEnabled;
  }
  setConnectionStatus("offline", false);
  wireEvents();
  updatePaceControls(null);
  updateCollapsiblePanels();
  render();
}

boot();
