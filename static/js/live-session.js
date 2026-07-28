function initLiveView(gigId, tracks) {
    var trackBtns = document.querySelectorAll('.track-btn');
    for (var i = 0; i < trackBtns.length; i++) {
        trackBtns[i].addEventListener('click', function() {
            var idx = parseInt(this.getAttribute('data-index'));
            selectTrack(gigId, idx);
        });
    }
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
