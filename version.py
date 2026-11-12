# -*- coding: utf-8 -*-
"""버전은 여기 한 곳에서만 정한다.
릴리스 태그(v<버전>)는 이 값과 같아야 하고(release.yml 이 확인), 설치 파일 버전은 빌드 때 이 값을 넘겨받는다
(installer.iss 에는 버전을 적지 않는다)."""
__version__ = "0.1.4"

RELEASES_API = "https://api.github.com/repos/seojaehong/gov-cert-login/releases/latest"
DOWNLOAD_PAGE = "https://github.com/seojaehong/gov-cert-login/releases/latest"


def _parts(v):
    return tuple(int(x) for x in v.strip().lstrip("vV").split("."))


def is_newer(remote, local=__version__):
    """remote 가 local 보다 새 버전이면 True. 형식이 이상하면 False(알림을 띄우지 않는다)."""
    try:
        return _parts(remote) > _parts(local)
    except ValueError:
        return False
