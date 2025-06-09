import numpy as np
import librosa
from dtw import dtw

def extract_pitch(y, sr):
    """
    F0(pitch) 궤적을 추출합니다.
    """
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y,
        fmin=librosa.note_to_hz('C2'),
        fmax=librosa.note_to_hz('C7')
    )
    return f0

def extract_rms(y):
    """
    RMS 에너지를 프레임별로 추출합니다.
    """
    return librosa.feature.rms(y=y)[0]

def extract_mfcc(y, sr, n_mfcc=13):
    """
    MFCC를 추출하고, 프레임별 평균 벡터를 시계열로 환원합니다.
    """
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    # 각 프레임(axis=1) 평균 내서 1차원 시계열 생성
    return mfcc.mean(axis=0)

def clean_series(x):
    """
    NaN을 그 시리즈의 평균값으로 대체하여 반환합니다.
    """
    x2 = x.copy()
    mask = np.isnan(x2)
    if np.any(mask):
        x2[mask] = np.nanmean(x2)
    return x2

def similarity_exp(dist, alpha=0.01):
    """
    dist → 0~1 사이 지수 스케일 유사도로 변환
    alpha: 민감도 조절(작을수록 완만)
    """
    return float(np.exp(-alpha * dist))

def calculate_dtw_similarity(a, b, alpha=0.01):
    """
    DTW로 두 시계열을 비교하고, 지수 스케일 유사도를 계산합니다.
    """
    x = clean_series(a)
    y = clean_series(b)
    alignment = dtw(
        x, y,
        dist_method=lambda u, v: abs(u - v),
        distance_only=True
    )
    dist = alignment.distance
    return similarity_exp(dist, alpha=alpha)

def calibrate(wav_path):
    """
    캘리브레이션용 짧은 녹음에서 F0를 뽑아
    사용자의 평균 피치(mean)와 표준편차(std)를 반환합니다.
    """
    y, sr = librosa.load(wav_path, sr=None)
    f0 = extract_pitch(y, sr)
    valid = f0[~np.isnan(f0)]
    mean = float(np.mean(valid))
    std  = float(np.std(valid))
    return mean, std

def analyze(learner_wav_path: str,
            native_wav_path: str,
            calib_stats: tuple[float, float] = None):
    """
    학습자·원어민 음성을 불러와
    pitch, rms, mfcc 피처를 추출하고,
    캘리브레이션 정보(calib_stats)를 반영하여 정규화한 뒤
    DTW 유사도를 계산합니다.
    피처별 유사도와 전체 유사도, 피처 시계열 및 시간축을 반환합니다.
    """
    # 1) 로드
    y_nat, sr_nat = librosa.load(native_wav_path, sr=None)
    y_lea, sr_lea = librosa.load(learner_wav_path, sr=None)

    # 2) 피처 추출
    f0_nat  = extract_pitch(y_nat, sr_nat)
    f0_lea  = extract_pitch(y_lea, sr_lea)
    rms_nat = extract_rms(y_nat)
    rms_lea = extract_rms(y_lea)
    mfcc_nat = extract_mfcc(y_nat, sr_nat)
    mfcc_lea = extract_mfcc(y_lea, sr_lea)

    # 3) 시간축 생성
    t_nat = librosa.times_like(f0_nat, sr=sr_nat).tolist()
    t_lea = librosa.times_like(f0_lea, sr=sr_lea).tolist()

    # 4) 정규화
    # 피치: 캘리브레이션 정보가 있으면 해당 mean/std 사용, 없으면 자체 z-score
    if calib_stats:
        mean, std = calib_stats
        f0n_nat = (f0_nat - mean) / (std + 1e-6)
        f0n_lea = (f0_lea - mean) / (std + 1e-6)
    else:
        # 내부 z-score
        def z_norm(x):
            valid = x[~np.isnan(x)]
            m, s = np.mean(valid), np.std(valid)
            return (x - m) / (s + 1e-6)
        f0n_nat = z_norm(f0_nat)
        f0n_lea = z_norm(f0_lea)

    # RMS, MFCC는 자체 z-score
    def z_norm_series(x):
        valid = x[~np.isnan(x)]
        m, s = np.mean(valid), np.std(valid)
        return (x - m) / (s + 1e-6)

    rmsn_nat  = z_norm_series(rms_nat)
    rmsn_lea  = z_norm_series(rms_lea)
    mfccn_nat = z_norm_series(mfcc_nat)
    mfccn_lea = z_norm_series(mfcc_lea)

    # 5) 유사도 계산 (alpha를 조절해 민감도 세팅)
    sim_stress = calculate_dtw_similarity(f0n_nat,  f0n_lea,  alpha=0.05)
    sim_rhythm = calculate_dtw_similarity(rmsn_nat, rmsn_lea, alpha=0.01)
    sim_mfcc   = calculate_dtw_similarity(mfccn_nat, mfccn_lea, alpha=0.01)
    overall    = (sim_stress + sim_rhythm + sim_mfcc) / 3
    # 0~1 사이 overall을 0~100점으로 변환 (정수)
    score = int(round(overall * 100))

    # 6) 결과 반환 (JSON 직렬화 가능하게)
    return {
        'stress_similarity':  float(sim_stress),
        'rhythm_similarity':  float(sim_rhythm),
        'mfcc_similarity':    float(sim_mfcc),
        'overall_similarity': float(overall),
        'score':              score,
        't_nat':              t_nat,
        't_lea':              t_lea,
        'f0_nat':             [None if np.isnan(x) else float(x) for x in f0_nat],
        'f0_lea':             [None if np.isnan(x) else float(x) for x in f0_lea],
    }
