import os
import uuid
from flask import Flask, render_template, request, jsonify, session
from audio_processing import analyze, calibrate  # calibrate 함수 추가

app = Flask(__name__)
# 세션을 사용한 캘리브레이션 저장을 위해 시크릿 키 설정 (실제 배포 시에는 랜덤 값으로 변경하세요)
app.secret_key = 'replace_with_a_random_secret_key'

# 녹음 파일 임시 저장 폴더
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    # static/audio 아래의 chapter 폴더 & 문장 목록을 읽어서 넘김
    audio_base = os.path.join(app.static_folder, 'audio')
    chapters = {}
    for ch in sorted(os.listdir(audio_base)):
        ch_path = os.path.join(audio_base, ch)
        if os.path.isdir(ch_path):
            wavs = [f for f in sorted(os.listdir(ch_path)) if f.lower().endswith('.wav')]
            sentences = [os.path.splitext(f)[0] for f in wavs]
            chapters[ch] = sentences
    return render_template('index.html', chapters=chapters)

@app.route('/sentence/<chapter>/<sentence>')
def sentence_page(chapter, sentence):
    # 선택된 챕터·문장 페이지
    return render_template('sentence.html', chapter=chapter, sentence=sentence)

@app.route('/calibrate', methods=['POST'])
def calibrate_route():
    """
    사용자가 녹음한 캘리브레이션 문장(audio) 파일을 받고,
    피치의 평균·표준편차를 계산하여 세션에 저장한 뒤 리턴합니다.
    """
    file = request.files.get('audio')
    if not file:
        return jsonify({'error': '녹음 파일이 필요합니다.'}), 400

    # 임시 저장
    fname = f"{uuid.uuid4()}.wav"
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    file.save(fpath)

    # 피치 평균·표준편차 계산
    mean, std = calibrate(fpath)

    # 파일 삭제
    os.remove(fpath)

    # 세션에 저장
    session['calib_pitch_mean'] = mean
    session['calib_pitch_std']  = std

    return jsonify({'calib_pitch_mean': mean, 'calib_pitch_std': std})

@app.route('/analyze', methods=['POST'])
def analyze_route():
    """
    사용자가 녹음한 문장(audio) 파일과 선택된 chapter/sentence를 받아
    캘리브레이션이 있으면 반영하여 분석 결과를 반환합니다.
    """
    chapter  = request.form.get('chapter')
    sentence = request.form.get('sentence')
    file     = request.files.get('audio')
    if not (chapter and sentence and file):
        return jsonify({'error': '파라미터가 부족합니다.'}), 400

    # 임시 녹음 저장
    fname = f"{uuid.uuid4()}.wav"
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    file.save(fpath)

    # 원어민 음성 경로
    native_path = os.path.join(app.static_folder, 'audio', chapter, f"{sentence}.wav")
    if not os.path.exists(native_path):
        os.remove(fpath)
        return jsonify({'error': '원어민 음성 파일을 찾을 수 없습니다.'}), 404

    # 세션에서 캘리브레이션 정보 읽기
    mean = session.get('calib_pitch_mean')
    std  = session.get('calib_pitch_std')
    calib_stats = (mean, std) if (mean is not None and std is not None) else None

    # 분석 실행
    result = analyze(
        learner_wav_path=fpath,
        native_wav_path=native_path,
        calib_stats=calib_stats  # 캘리브레이션 정보 전달
    )

    # 임시 파일 정리
    os.remove(fpath)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
