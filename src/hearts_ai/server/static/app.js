const SCHEMA_VERSION = 1;
const RECONNECT_DELAY_MS = 1500;
const DEFAULT_PACE_MS = 900;
const FAST_FORWARD_PACE_MS = 220;
const TRICK_HOLD_MS = 1500;

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
  joinCode: document.getElementById("joinCode"),
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

  dom.autoplayBtn.textContent = appState.autoplayEnabled ? "Pause" : "Play";
  dom.paceRange.value = String(appState.paceMs);
  dom.fastForwardToggle.checked = appState.fastForwardToMyTurn;
  dom.paceValue.textContent = `${appState.paceMs}ms`;
}

function canControlPace(snapshot) {
  return Boolean(snapshot && snapshot.viewer_can_control_pace);
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
      appState.snapshot = response.snapshot;
      render();
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

async function createTable() {
  const displayName = dom.displayName.value.trim();
  if (!displayName) {
    setInfo("Enter a display name first.");
    return;
  }

  const targetScore = Number(dom.targetScore.value);
  const seedRaw = dom.seed.value.trim();
  const payload = { display_name: displayName, target_score: Number.isFinite(targetScore) ? targetScore : 50 };
  if (seedRaw) {
    payload.seed = Number(seedRaw);
  }

  try {
    const created = await apiRequest("/tables", "POST", payload);
    appState.tableCode = created.table_code;
    appState.playerSecret = created.player_secret;
    appState.displayName = displayName;
    dom.joinCode.value = created.table_code;
    appState.selectedPassCards.clear();
    saveSession();
    await fetchSnapshot();
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
    saveSession();
    await fetchSnapshot();
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
  appState.snapshot = snapshot;
  render();
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
      appState.snapshot = message.payload || null;
      render();
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

async function addBot(seat) {
  if (!appState.tableCode) {
    setInfo("Create or join a table first.");
    return;
  }
  try {
    await apiRequest(`/tables/${appState.tableCode}/bots/${seat}`, "POST");
    await fetchSnapshot();
  } catch (error) {
    setInfo(error.message);
  }
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
  head.innerHTML = `<span>P${seat.seat}</span><span>${seat.kind}</span>`;

  const name = document.createElement("div");
  name.className = "seat-name";
  name.textContent = seat.display_name || (seat.kind === "open" ? "Open seat" : "Bot");

  const metrics = document.createElement("div");
  metrics.className = "seat-metrics";

  const totalMetric = document.createElement("span");
  totalMetric.className = "seat-metric";
  totalMetric.textContent = `Total ${snapshot.scores[String(seat.seat)] || 0}`;

  const handMetric = document.createElement("span");
  handMetric.className = "seat-metric";
  handMetric.textContent = `Hand ${snapshot.seat_hand_points[String(seat.seat)] || 0}`;

  metrics.append(totalMetric, handMetric);

  seatBox.append(head, name, metrics);

  if (seat.kind === "open" && appState.playerSecret) {
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
    botBtn.addEventListener("click", () => addBot(seat.seat));
    actions.appendChild(botBtn);

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
    dom.passHint.textContent = "Pass submitted. Waiting for other players.";
  } else {
    dom.passHint.textContent = `Select ${passCount} cards to pass.`;
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
  const canPlay = snapshot.phase === "playing" && snapshot.turn === snapshot.viewer_seat;
  const orderedHand = sortCardsForHand(snapshot.viewer_hand || []);

  for (const card of orderedHand) {
    const button = document.createElement("button");
    button.className = "card-btn";
    button.appendChild(createCardFace(card));
    button.title = `Play ${card}`;
    if (legal.has(card)) {
      button.classList.add("legal");
    }

    if (canPlay && legal.has(card)) {
      button.classList.add("play");
      button.addEventListener("click", () => playCard(card));
    } else {
      button.disabled = true;
    }

    dom.handGrid.appendChild(button);
  }
}

function render(snapshot = appState.snapshot) {
  dom.tableCodeValue.textContent = appState.tableCode || "-";
  if (!snapshot) {
    dom.phaseValue.textContent = "-";
    dom.viewerSeatValue.textContent = "spectator";
    dom.tableSection.classList.add("hidden");
    clearAdvanceTimer();
    clearTrickHoldTimer();
    appState.hasRenderedSnapshot = false;
    updatePaceControls(null);
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
    if (snapshot.viewer_seat !== null && snapshot.turn === snapshot.viewer_seat) {
      setInfo("Your turn. Play a legal card.");
    } else if (snapshot.turn !== null) {
      setInfo(`Waiting on P${snapshot.turn}.`);
    } else {
      setInfo("Waiting for next turn.");
    }
  } else if (snapshot.phase === "game_over") {
    setInfo("Game over. Create another table to play again.");
  }

  renderTable(snapshot);
  renderPassPanel(snapshot);
  renderHand(snapshot);
  updatePaceControls(snapshot);
  appState.hasRenderedSnapshot = true;
  scheduleAutoAdvance(snapshot);
}

function wireEvents() {
  dom.createBtn.addEventListener("click", createTable);
  dom.joinBtn.addEventListener("click", joinTable);
  dom.reconnectBtn.addEventListener("click", reconnectSession);
  dom.submitPassBtn.addEventListener("click", submitPass);
  dom.autoplayBtn.addEventListener("click", () => {
    appState.autoplayEnabled = !appState.autoplayEnabled;
    updatePaceControls();
    scheduleAutoAdvance();
  });
  dom.stepBtn.addEventListener("click", () => {
    void advanceOneAction();
  });
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
  setConnectionStatus("offline", false);
  wireEvents();
  updatePaceControls(null);
  render();
}

boot();
