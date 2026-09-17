def download_file(url, save_path):
    print(f"📥 미디어 파일 다운로드 중: {url}")
    res = requests.get(url, stream=True)
    
    try:
        res.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"❌ 다운로드 HTTP 에러 발생: {e}")
        raise RuntimeError(f"Download HTTP Error: {e}")

    with open(save_path, 'wb') as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)
            
    file_size = os.path.getsize(save_path)
    print(f"📥 다운로드 완료 - 파일 크기: {file_size} bytes")
    
    # 💡 파일이 너무 작으면(에러 페이지 등) 즉시 에러를 발생시켜 FFmpeg 실행을 차단
    if file_size < 5000:
        try:
            with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(500)
                print(f"⚠️ 다운로드된 파일이 정상적인 영상이 아닙니다. 내용: {content}")
        except Exception:
            pass
        raise RuntimeError("Downloaded file is invalid or an HTML error page (not an MP4).")
        
    return save_path
