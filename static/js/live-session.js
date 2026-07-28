var ws = null;
var wsReconnectTimer = null;

function initLiveView(gigId, tracks) {
    var trackBtns = document.querySelectorAll('.track-btn');

    for (var i = 0; i < trackBtns.length; i++) {
        trackBtns[i].addEventListener('click', function() {
            var idx = parseInt(this.getAttribute('data-index'));
            selectTrack(gigId, idx);
        });
    }

    connectWebSocket(gigId);
}

function selectTrack(gigId, trackIndex) {
    var track = TRACKS[trackIndex];
    if (!track || !track.chart) return;
    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/select/' + encodeURIComponent(gigId) + '/' + trackIndex, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({}));
    window.location.href = '/chart/' + encodeURIComponent(gigId) + '/' + encodeURIComponent(track.chart);
}

function updateUI(activeTrack, track) {
    var btns = document.querySelectorAll('.track-btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', i === activeTrack);
    }
}

function connectWebSocket(gigId) {
    if (ws && ws.readyState <= 1) {
        return;
    }
    var protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = protocol + '//' + location.host + '/ws';
    try {
        ws = new WebSocket(url);
    } catch (e) {
        scheduleReconnect();
        return;
    }
    ws.onopen = function() {
        if (wsReconnectTimer) {
            clearTimeout(wsReconnectTimer);
            wsReconnectTimer = null;
        }
    };
    ws.onmessage = function(evt) {
        try {
            var msg = JSON.parse(evt.data);
            if (msg.type === 'track_changed' && msg.gig_id === gigId) {
                updateUI(msg.active_track, msg.track);
            }
        } catch (e) {}
    };
    ws.onclose = function() {
        scheduleReconnect();
    };
    ws.onerror = function() {
        ws.close();
    };
}

function scheduleReconnect() {
    if (wsReconnectTimer) return;
    wsReconnectTimer = setTimeout(function() {
        wsReconnectTimer = null;
        connectWebSocket(GIG_ID);
    }, 2000);
}
