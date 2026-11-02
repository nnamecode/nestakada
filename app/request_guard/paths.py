"""Bounded classification only: never rewrite a routing identity or read files."""
import re
from urllib.parse import unquote

MAX_PATH_CHARACTERS = 8192
SIGNATURES = ('traversal', 'dotfile', 'wordpress', 'php-tool', 'phpunit',
              'executable', 'backup', 'cgi', 'malformed', 'oversize')
_WORDPRESS = re.compile(r'^/(?:wp-admin|wp-includes|wp-content)(?:/|$)')
_PHP_TOOL = re.compile(r'^/phpmyadmin(?:/|$)')
_EXECUTABLE = re.compile(r'\.(?:php[0-9]?|phtml|phar|asp|aspx|jsp)(?:/|$)')
_BACKUP = re.compile(r'(?:\.(?:bak|old|orig|swp|sql|sqlite|sqlite3|tar|tar\.gz|zip)|~)$')
_CGI = re.compile(r'^/cgi-bin(?:/|$)')
_BAD_ESCAPE = re.compile(r'%(?![0-9a-fA-F]{2})')


def classify_path(path):
    """Accept a PATH, not a query/URL; at most three finite interpretations."""
    if type(path) is not str or not path.startswith('/'):
        return 'malformed'
    if len(path) > MAX_PATH_CHARACTERS:
        return 'oversize'
    if any(0xD800 <= ord(char) <= 0xDFFF for char in path):
        return 'malformed'
    current = path
    for step in range(3):
        shadow = re.sub(r'/+', '/', current.lower().replace('\\', '/'))
        parts = shadow.split('/')[1:]
        if '\\' in current or any(part in ('.', '..') for part in parts):
            return 'traversal'
        if any(part.startswith('.') and not (index == 0 and part == '.well-known')
               for index, part in enumerate(parts)):
            return 'dotfile'
        if _WORDPRESS.search(shadow) or shadow == '/wp-login.php':
            return 'wordpress'
        if _PHP_TOOL.search(shadow):
            return 'php-tool'
        if shadow.startswith('/vendor/phpunit/'):
            return 'phpunit'
        if _EXECUTABLE.search(shadow):
            return 'executable'
        if _BACKUP.search(shadow):
            return 'backup'
        if _CGI.search(shadow):
            return 'cgi'
        if _BAD_ESCAPE.search(current) or any(ord(char) < 32 or ord(char) == 127 for char in current):
            return 'malformed'
        if step == 2 or '%' not in current:
            break
        try:
            decoded = unquote(current, encoding='utf-8', errors='strict')
        except UnicodeError:
            return 'malformed'
        if decoded == current:
            break
        current = decoded
    return None


def classify_target(target):
    """Only for raw request targets/registry entries; query is not a signature."""
    if type(target) is not str:
        return 'malformed'
    return classify_path(target.partition('?')[0])
