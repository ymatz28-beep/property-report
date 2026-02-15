"""Google Drive連携モジュール - OAuth 2.0認証 + ファイル取得"""

import json
import tempfile
from pathlib import Path
from datetime import datetime

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

# Drive APIのスコープ（読み取り専用）
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

BASE_DIR = Path(__file__).parent.parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"


def check_available() -> bool:
    """Google Drive連携が利用可能か確認"""
    if not HAS_GOOGLE:
        return False
    if not CREDENTIALS_PATH.exists():
        return False
    return True


def authenticate() -> "Credentials":
    """OAuth 2.0認証を実行し、認証情報を返す"""
    if not HAS_GOOGLE:
        raise RuntimeError(
            "Google API ライブラリがインストールされていません。\n"
            "  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )

    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json が見つかりません: {CREDENTIALS_PATH}\n"
            "  Google Cloud Console からダウンロードしてください。"
        )

    creds = None

    # 保存済みトークンの読み込み
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # トークンが無効または期限切れの場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("       トークンを更新中...")
            creds.refresh(Request())
        else:
            print("       ブラウザで認証を行います...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # トークンを保存
        TOKEN_PATH.write_text(creds.to_json())
        print("       認証情報を保存しました")

    return creds


def get_service(creds):
    """Google Drive APIサービスオブジェクトを取得"""
    return build("drive", "v3", credentials=creds)


def list_folder_files(service, folder_id: str, mime_filter: str | None = None) -> list[dict]:
    """フォルダ内のファイル一覧を取得（更新日降順）"""
    query = f"'{folder_id}' in parents and trashed = false"
    if mime_filter:
        query += f" and mimeType = '{mime_filter}'"

    results = service.files().list(
        q=query,
        pageSize=50,
        fields="files(id, name, mimeType, modifiedTime, size)",
        orderBy="modifiedTime desc",
    ).execute()

    return results.get("files", [])


def find_tax_return_pdfs(service, folder_id: str) -> list[dict]:
    """確定申告フォルダからPDFファイルを検索（最新年度優先）"""
    # まずフォルダ直下のPDFを検索
    pdfs = list_folder_files(service, folder_id, mime_filter="application/pdf")

    # サブフォルダも検索（年度別フォルダがある場合）
    subfolders = list_folder_files(
        service, folder_id, mime_filter="application/vnd.google-apps.folder"
    )

    for subfolder in subfolders:
        sub_pdfs = list_folder_files(
            service, subfolder["id"], mime_filter="application/pdf"
        )
        for pdf in sub_pdfs:
            pdf["parent_folder"] = subfolder["name"]
        pdfs.extend(sub_pdfs)

    # 年度でソート（ファイル名やフォルダ名から年度を推定）
    def extract_year(f):
        name = f.get("parent_folder", "") + f["name"]
        import re
        # 令和X年、R X、20XX年 などのパターン
        match = re.search(r"(?:令和|R)\s*(\d+)", name)
        if match:
            return 2018 + int(match.group(1))
        match = re.search(r"(20\d{2})", name)
        if match:
            return int(match.group(1))
        return 0

    pdfs.sort(key=extract_year, reverse=True)
    return pdfs


def download_file(service, file_id: str, file_name: str) -> Path:
    """Google DriveからファイルをダウンロードしてTempパスを返す"""
    import io

    request = service.files().get_media(fileId=file_id)
    tmp_dir = Path(tempfile.mkdtemp(prefix="gdrive_"))
    file_path = tmp_dir / file_name

    fh = io.FileIO(str(file_path), "wb")
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.close()
    return file_path


def search_files(service, query_text: str, max_results: int = 10) -> list[dict]:
    """Google Drive全体からファイルを検索"""
    query = f"name contains '{query_text}' and trashed = false"
    results = service.files().list(
        q=query,
        pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime, parents)",
        orderBy="modifiedTime desc",
    ).execute()
    return results.get("files", [])


def fetch_tax_returns(config: dict) -> tuple[list[Path], dict]:
    """
    確定申告PDFをGoogle Driveから取得

    Returns:
        (ダウンロードしたPDFパスのリスト, メタデータ dict)
    """
    gdrive_config = config.get("google_drive", {})
    folder_id = gdrive_config.get("folder_id")

    if not folder_id:
        raise ValueError("config.yaml に google_drive.folder_id が設定されていません")

    creds = authenticate()
    service = get_service(creds)

    print("       確定申告フォルダを検索中...")
    pdfs = find_tax_return_pdfs(service, folder_id)

    if not pdfs:
        raise FileNotFoundError(
            f"フォルダ内にPDFが見つかりませんでした (folder_id: {folder_id})"
        )

    # 最新年度のPDFをダウンロード（最大5ファイル）
    max_download = gdrive_config.get("max_files", 5)
    downloaded = []
    metadata = {
        "fetch_time": datetime.now().isoformat(),
        "folder_id": folder_id,
        "files": [],
    }

    for pdf in pdfs[:max_download]:
        print(f"       ダウンロード: {pdf['name']}")
        path = download_file(service, pdf["id"], pdf["name"])
        downloaded.append(path)
        metadata["files"].append({
            "name": pdf["name"],
            "id": pdf["id"],
            "modified": pdf.get("modifiedTime", ""),
            "parent_folder": pdf.get("parent_folder", ""),
        })

    return downloaded, metadata
