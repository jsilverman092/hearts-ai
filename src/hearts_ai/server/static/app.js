const SCHEMA_VERSION = 1;
const RECONNECT_DELAY_MS = 1500;

const appState = {
  tableCode: null,
  playerSecret: null,
  displayName: "",
  ws: null,
  reconnectTimer: null,
  snapshot: null,
  selectedPassCards: new Set(),
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
  seatsGrid: document.getElementById("seatsGrid"),
  scoreGrid: document.getElementById("scoreGrid"),
  trickGrid: document.getElementById("trickGrid"),
  metaLine: document.getElementById("metaLine"),
  infoLine: document.getElementById("infoLine"),
  handGrid: document.getElementById("handGrid"),
  passPanel: document.getElementById("passPanel"),
  passCards: document.getElementById("passCards"),
  passHint: document.getElementById("passHint"),
  submitPassBtn: document.getElementById("submitPassBtn"),
};

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

function renderSeats(snapshot) {
  dom.seatsGrid.innerHTML = "";

  for (const seat of snapshot.seats) {
    const seatBox = document.createElement("div");
    seatBox.className = "seat";
    if (snapshot.viewer_seat === seat.seat) {
      seatBox.classList.add("you");
    }
    if (seat.kind === "bot") {
      seatBox.classList.add("bot");
    }

    const head = document.createElement("div");
    head.className = "seat-head";
    head.innerHTML = `<span>P${seat.seat}</span><span>${seat.kind}</span>`;

    const name = document.createElement("div");
    name.className = "seat-name";
    name.textContent = seat.display_name || (seat.kind === "open" ? "Open seat" : "Bot");

    const actions = document.createElement("div");
    actions.className = "chip-row";

    if (seat.kind === "open" && appState.playerSecret) {
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
    }

    seatBox.append(head, name, actions);
    dom.seatsGrid.appendChild(seatBox);
  }
}

function renderScores(snapshot) {
  dom.scoreGrid.innerHTML = "";
  for (const seat of snapshot.seats) {
    const row = document.createElement("div");
    row.className = "chip-row";
    const badge = document.createElement("span");
    badge.className = "chip";
    badge.textContent = `P${seat.seat}`;
    const value = document.createElement("span");
    value.className = "chip";
    value.textContent = String(snapshot.scores[String(seat.seat)] || 0);
    row.append(badge, value);
    dom.scoreGrid.appendChild(row);
  }
}

function renderTrick(snapshot) {
  dom.trickGrid.innerHTML = "";
  if (!snapshot.current_trick || snapshot.current_trick.length === 0) {
    const empty = document.createElement("span");
    empty.className = "hint";
    empty.textContent = "No cards in trick.";
    dom.trickGrid.appendChild(empty);
    return;
  }

  for (const play of snapshot.current_trick) {
    const token = document.createElement("span");
    token.className = "chip";
    token.textContent = `P${play.player_id}: ${play.card}`;
    dom.trickGrid.appendChild(token);
  }
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

  for (const card of snapshot.viewer_hand) {
    const button = document.createElement("button");
    button.className = "card-btn";
    button.textContent = card;
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

  for (const card of snapshot.viewer_hand || []) {
    const button = document.createElement("button");
    button.className = "card-btn";
    button.textContent = card;
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
    return;
  }

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

  renderSeats(snapshot);
  renderScores(snapshot);
  renderTrick(snapshot);
  renderPassPanel(snapshot);
  renderHand(snapshot);
}

function wireEvents() {
  dom.createBtn.addEventListener("click", createTable);
  dom.joinBtn.addEventListener("click", joinTable);
  dom.reconnectBtn.addEventListener("click", reconnectSession);
  dom.submitPassBtn.addEventListener("click", submitPass);
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
  render();
}

boot();

