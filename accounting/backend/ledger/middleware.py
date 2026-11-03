from urllib.parse import urlsplit
from django.http import JsonResponse


class LocalOnlyMiddleware:
  def __init__(self, get_response):
    self.get_response = get_response

  def __call__(self, request):
    # HTTPは閲覧専用。変更はローカルの管理コマンドだけで行う。
    request.get_host()
    origin = request.headers.get('Origin')
    if origin and urlsplit(origin).hostname not in {'localhost', '127.0.0.1'}:
      return JsonResponse({'error': 'ローカル接続のみ利用できます。'}, status=403)
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
      return JsonResponse({'error': '家計APIは閲覧専用です。'}, status=405)
    response = self.get_response(request)
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
