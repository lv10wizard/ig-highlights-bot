
BASE_URL = 'https://www.gfycat.com'

# https://developers.gfycat.com/api/?curl#creating-gfycats
BASE_API_URL = 'https://api.gfycat.com/v1'

TOKEN_URL = BASE_API_URL + '/oauth/token'

# data=json.dumps({ ... })
# https://developers.gfycat.com/api/?curl#gfycat-creation-parameters-and-options
FETCH_URL = BASE_API_URL + '/gfycats'
# .format(gfyname)
FETCH_STATUS_URL = BASE_API_URL + '/gfycats/fetch/status/{0}'

# the following require headers={'Authorization': 'Bearer {access_token}'}
# data=json.dumps({'folderName': '...'})
ALBUM_FOLDERS_URL = BASE_API_URL + '/me/album-folders'
# .format(album_folders['id'])
ALBUMS_URL = BASE_API_URL + '/me/albums/{0}'
ALBUMS_NAME_URL = ALBUMS_URL + '/name'
ALBUMS_ORDER_URL = ALBUMS_URL + '/order'

