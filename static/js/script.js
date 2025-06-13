// static/js/script.js

document.addEventListener('DOMContentLoaded', () => {
  // --- 캘리브레이션 섹션 요소 ---
  const calibRecordButton = document.getElementById('calibRecordButton');
  const calibStopButton   = document.getElementById('calibStopButton');
  const calibUploadButton = document.getElementById('calibUploadButton');
  const calibStatus       = document.getElementById('calibStatus');
  let calibRecorder, calibAudioChunks = [], recordedCalibBlob;

  // --- 연습 섹션 요소 ---
  const recordButton    = document.getElementById('recordButton');
  const stopButton      = document.getElementById('stopButton');
  const analyzeButton   = document.getElementById('analyzeButton');
  const reRecordButton  = document.getElementById('reRecordButton');
  const statusLabel     = document.getElementById('status');
  const recordedAudio   = document.getElementById('recordedAudio');
  let mediaRecorder, audioChunks = [], recordedBlob;

  // 캘리브레이션 녹음 시작
  calibRecordButton.addEventListener('click', async () => {
    calibStatus.textContent = '🔄 마이크 권한 요청 중...';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      calibRecorder    = new MediaRecorder(stream);
      calibAudioChunks = [];

      calibRecorder.ondataavailable = e => calibAudioChunks.push(e.data);
      calibRecorder.onstart = () => {
        calibStatus.textContent        = '🔴 캘리브레이션 녹음 중...';
        calibRecordButton.disabled     = true;
        calibStopButton.disabled       = false;
        calibUploadButton.disabled     = true;
      };
      calibRecorder.onstop = () => {
        recordedCalibBlob = new Blob(calibAudioChunks, { type: 'audio/wav' });
        calibStatus.textContent    = '✅ 녹음 완료 — “캘리브레이션 적용” 버튼을 눌러주세요.';
        calibUploadButton.disabled = false;
      };

      calibRecorder.start();
    } catch (err) {
      calibStatus.textContent = '❌ 오류: ' + err.message;
    }
  });

  // 캘리브레이션 녹음 중지
  calibStopButton.addEventListener('click', () => {
    if (calibRecorder && calibRecorder.state === 'recording') {
      calibRecorder.stop();
      calibStopButton.disabled = true;
    }
  });

  // 캘리브레이션 서버 전송
  calibUploadButton.addEventListener('click', async () => {
    if (!recordedCalibBlob) return;
    calibStatus.textContent = '⏳ 캘리브레이션 적용 중...';
    const form = new FormData();
    form.append('audio', recordedCalibBlob, 'calibration.wav');

    try {
      const res  = await fetch('/calibrate', { method: 'POST', body: form });
      const data = await res.json();
      if (data.error) {
        calibStatus.textContent = '❌ 캘리브레이션 오류: ' + data.error;
        return;
      }
      calibStatus.textContent = '✅ 캘리브레이션 완료!';
      document.getElementById('calibration').style.display = 'none';
      document.getElementById('practice').style.display    = 'block';
    } catch (err) {
      calibStatus.textContent = '❌ 서버 오류: ' + err.message;
    }
  });

  // --- 연습 섹션 동작 ---

  // 녹음 시작
  recordButton.addEventListener('click', async () => {
    statusLabel.textContent = '🔄 마이크 권한 요청 중...';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks   = [];

      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstart = () => {
        statusLabel.textContent   = '🔴 녹음 중...';
        recordButton.disabled     = true;
        stopButton.disabled       = false;
        analyzeButton.disabled    = true;
        reRecordButton.style.display = 'none';
      };
      mediaRecorder.onstop = () => {
        recordedBlob = new Blob(audioChunks, { type: 'audio/wav' });
        recordedAudio.src          = URL.createObjectURL(recordedBlob);
        recordedAudio.style.display = 'block';
        statusLabel.textContent    = '✅ 녹음 완료 — “분석하기” 버튼을 눌러주세요.';
        analyzeButton.disabled     = false;
        reRecordButton.style.display = 'inline-block';
      };

      mediaRecorder.start();
    } catch (err) {
      statusLabel.textContent = '❌ 오류: ' + err.message;
    }
  });

  // 녹음 중지
  stopButton.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      stopButton.disabled = true;
    }
  });

  // 다시 녹음
  reRecordButton.addEventListener('click', () => {
    recordedBlob   = null;
    audioChunks    = [];
    recordedAudio.src          = '';
    recordedAudio.style.display = 'none';
    statusLabel.textContent    = '🔄 다시 녹음해주세요.';
    recordButton.disabled      = false;
    stopButton.disabled        = true;
    analyzeButton.disabled     = true;
    reRecordButton.style.display = 'none';
  });

  // 분석하기
  analyzeButton.addEventListener('click', async () => {
    if (!recordedBlob) return;
    statusLabel.textContent = '⏳ 분석 중...';
    analyzeButton.disabled  = true;

    const form = new FormData();
    form.append('chapter',  chapter);
    form.append('sentence', sentence);
    form.append('audio',    recordedBlob, 'record.wav');

    try {
      const res  = await fetch('/analyze', { method: 'POST', body: form });
      const data = await res.json();
      if (data.error) {
        statusLabel.textContent = '❌ 분석 오류: ' + data.error;
        return;
      }
      statusLabel.textContent = '✅ 분석 완료';
      // 1) 점수 보여주기
      const scoreEl = document.getElementById('scoreDisplay');
      scoreEl.textContent = `점수: ${data.score}점`;
      // 2) 차트 그리기
      showResultCharts(data);
    } catch (err) {
      statusLabel.textContent = '❌ 서버 오류: ' + err.message;
    }
  });

  // 결과 차트(bar + line) 그리기
  function showResultCharts(data) {
    // 1) 유사도 막대 차트
    const ctxBar = document.getElementById('resultChart').getContext('2d');
    new Chart(ctxBar, {
      type: 'bar',
      data: {
        labels: ['Stress', 'Rhythm', 'MFCC', 'Overall'],
        datasets: [{
          label: '유사도 (0~1)',
          data: [
            data.stress_similarity,
            data.rhythm_similarity,
            data.mfcc_similarity,
            data.overall_similarity
          ]
        }]
      },
      options: {
        scales: { y: { beginAtZero: true, max: 1 } }
      }
    });

    // 2) 피치 컨투어 라인 차트
    const ctxLine = document.getElementById('pitchChart').getContext('2d');
    new Chart(ctxLine, {
      type: 'line',
      data: {
        labels: data.t_nat,
        datasets: [
          {
            label: '원어민 F0',
            data: data.f0_nat,
            fill: false
          },
          {
            label: '내 발음 F0',
            data: data.f0_lea,
            fill: false
          }
        ]
      },
      options: {
        scales: {
          x: { title: { display: true, text: '시간 (s)' } },
          y: { title: { display: true, text: 'F0 (Hz)' } }
        }
      }
    });
  }
});
