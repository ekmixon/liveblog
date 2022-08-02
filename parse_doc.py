# _*_ coding:utf-8 _*_
# This is called by app.py: parsed_document = parse_doc.parse(doc)
import logging
import re
import app_config
import datetime
import pytz
from shortcode import process_shortcode
import cPickle as pickle
from bs4 import BeautifulSoup
from pymongo import MongoClient
import xlrd

logging.basicConfig(format=app_config.LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(app_config.LOG_LEVEL)

end_liveblog_regex = re.compile(ur'^\s*[Ee][Nn][Dd]\s*$',
                                re.UNICODE)

new_post_marker_regex = re.compile(ur'^\s*\+{50,}\s*$',
                                   re.UNICODE)
post_end_marker_regex = re.compile(ur'^\s*-{50,}\s*$',
                                   re.UNICODE)

frontmatter_marker_regex = re.compile(ur'^\s*-{3}\s*$',
                                      re.UNICODE)

extract_metadata_regex = re.compile(ur'^(.*?):(.*)$',
                                    re.UNICODE)

shortcode_regex = re.compile(ur'^\s*\[%\s*.*\s*%\]\s*$', re.UNICODE)

internal_link_regex = re.compile(ur'(\[% internal_link\s+.*?\s*%\])',
                                 re.UNICODE)

author_initials_regex = re.compile(ur'^(.*)\((\w{2,3})\)\s*$', re.UNICODE)


def is_post_marker(tag):
    """
    Checks for the beginning of a new post
    """
    text = tag.get_text()
    return bool(m := new_post_marker_regex.match(text))


def is_post_end_marker(tag):
    """
    Checks for the beginning of a new post
    """
    text = tag.get_text()
    return bool(m := post_end_marker_regex.match(text))


def find_pinned_post(posts):
    """
    Find the pinned post
    first test if it is at the beginning to avoid looping through
    all the posts
    """
    idx = 0
    try:
        posts[idx]['pinned']
    except KeyError:
        logger.warning("Pinned post is not the first on the live document")
        found = False
        for idx, post in enumerate(posts):
            try:
                if post['pinned'] == 'yes':
                    found = True
                    break
            except KeyError:
                continue
        if not found:
            idx = None

    return idx


def order_posts(posts):
    """
    Order posts in reverse chronological order
    Except for the pinned post
    """
    try:
        ordered_posts = sorted(posts, key=lambda x: x['timestamp'],
                               reverse=True)
    except ValueError, e:
        logger.error("this should not happen, could not order %s" % e)
        ordered_posts = posts
    return ordered_posts


def insert_sponsorship(ordered_posts):
    """
    1. Find the length of the ordered posts
    2. If the length is greater than sponsorship postition,
    3. Insert sponsorship
    """
    if app_config.SPONSORSHIP_POSITION == -1:
        return ordered_posts

    published_count = 0
    insert = False
    for idx, post in enumerate(ordered_posts):
        try:
            if (post['published'] == 'yes'):
                published_count += 1
            if (published_count >= app_config.SPONSORSHIP_POSITION):
                insert = True
                break
        except KeyError:
            logger.warning(f"Post does not have published metadata {post}")
            continue
    if insert:
        SPONSORSHIP = {
            'slug': 'sponsorship',
            'published': 'yes',
            'contents': 'This is the sponsorship post.'
        }

        ordered_posts.insert(idx + 1, SPONSORSHIP)

    return ordered_posts


def compose_pinned_post(post):
    """
    1.Verify that this is the pinned post
    2.Obtain the results json from the results rig
    3.Compose the HTML for the compact graphic
    """
    pinned_post = post
    # Get the timestamps collection
    client = MongoClient(app_config.MONGODB_URL)
    database = client['liveblog']
    collection = database.pinned
    try:
        post['pinned']
    except KeyError:
        logger.error("First post should always be the pinned post")

    # Cache pinned post contents
    if post['published mode'] == 'yes':
        # Update mongodb cache
        post['cached_contents'] = post['contents']
        post['cached_headline'] = post['headline']
        logger.debug(f"update cached headline to {post['headline']}")
        collection.update({'_id': post['slug']},
                          {'cached_contents': post['contents'],
                           'cached_headline': post['headline']})

    elif result := collection.find_one({'_id': post['slug']}):
        logger.debug(f"found pinned post {post['slug']}")
        post['cached_contents'] = result['cached_contents']
        post['cached_headline'] = result['cached_headline']
        logger.debug(f"returning cached headline {post['cached_headline']}")
    else:
        logger.debug(f"did not find pinned post {post['slug']}")
        collection.insert({
            '_id': post['slug'],
            'cached_contents': post['contents'],
            'cached_headline': post['headline'],
        })
        post['cached_contents'] = post['contents']
        post['cached_headline'] = post['headline']
    return pinned_post


def add_last_timestamp(posts):
    """
    add last updated liveblog timestamp
    """
    return posts[0]['timestamp'] if posts else None


def process_inline_internal_link(m):
    raw_shortcode = m.group(1)
    fake_p = BeautifulSoup(f'<p>{raw_shortcode}</p>', "html.parser")
    return process_shortcode(fake_p)


def process_headline(contents):
    logger.debug('--process_headline start--')
    headline = None
    for tag in contents:
        if tag.name == "h1":
            headline = tag.get_text()
        else:
            logger.warning(f'unexpected tag found: Ignore {tag.get_text()}')
    if not headline:
        logger.error(f'Did not find headline on post. Contents: {contents}')
    return headline


def add_author_metadata(metadata, authors):
    """
    extract author data from dict and add to metadata
    """
    # Ignore authors parsing for pinned post
    try:
        if metadata['pinned']:
            return
    except KeyError:
        pass

    raw_authors = metadata.pop('authors')
    authors_result = []
    bits = raw_authors.split(',')
    for bit in bits:
        author = { 'page': '' }
        if m := author_initials_regex.match(bit):
            key = m.group(2)
            try:
                author['name'] = authors[key]['name']
                author['page'] = authors[key]['page']
            except KeyError:
                logger.warning(f'did not find author in dictionary {key}')
                author['name'] = m.group(1).strip()
        else:
            logger.debug(f"Author not in dictionary: {raw_authors}")
            author['name'] = bit
        authors_result.append(author)
    if not len(authors):
        # Add a default author to avoid erroing out
        author['name'] = 'NPR Staff'
        author['page'] = 'http://www.npr.org/'
        authors_result.append(author)
    metadata['authors'] = authors_result


def process_metadata(contents):
    logger.debug('--process_metadata start--')
    metadata = {}
    for tag in contents:
        text = tag.get_text()
        if m := extract_metadata_regex.match(text):
            key = m.group(1).strip().lower()
            value = m.group(2).strip()
            if key != 'authors':
                value = value.lower()
            metadata[key] = value
        else:
            logger.error(f'Could not parse metadata. Text: {text}')
    logger.debug(f"metadata: {metadata}")
    return metadata


def process_post_contents(contents):
    """
    Process post copy content
    In particular parse and generate HTML from shortcodes
    """
    logger.debug('--process_post_contents start--')

    parsed = []
    for tag in contents:
        text = tag.get_text()
        if m := shortcode_regex.match(text):
            parsed.append(process_shortcode(tag))
        else:
            # Parsed searching and replacing for inline internal links
            parsed_tag = internal_link_regex.sub(process_inline_internal_link,
                                                 unicode(tag))
            logger.debug(f'parsed tag: {parsed_tag}')
            parsed.append(parsed_tag)
    return ''.join(parsed)


def parse_raw_posts(raw_posts, authors):
    """
    parse raw posts into an array of post objects
    """

    # Divide each post into its subparts
    # - Headline
    # - FrontMatter
    # - Contents
    posts = []

    # Get the timestamps collection
    client = MongoClient(app_config.MONGODB_URL)
    database = client['liveblog']
    collection = database.timestamps
    for raw_post in raw_posts:
        marker_counter = 0
        post_raw_headline = []
        post_raw_metadata = []
        post_raw_contents = []
        for tag in raw_post:
            text = tag.get_text()
            m = frontmatter_marker_regex.match(text)
            if m:
                marker_counter += 1
            elif marker_counter == 0:
                post_raw_headline.append(tag)
            elif marker_counter == 1:
                post_raw_metadata.append(tag)
            else:
                post_raw_contents.append(tag)
        post = {'headline': process_headline(post_raw_headline)}
        metadata = process_metadata(post_raw_metadata)
        add_author_metadata(metadata, authors)
        for k, v in metadata.iteritems():
            post[k] = v
        post[u'contents'] = process_post_contents(post_raw_contents)
        posts.append(post)

        # Retrieve timestamp from mongo
        utcnow = datetime.datetime.utcnow()
        # Ignore pinned post timestamp generation
        if 'pinned' in post:
            continue
        if post['published'] == 'yes':
            if result := collection.find_one({'_id': post['slug']}):
                logger.debug(f"post {post['slug']} timestamp: retrieved from cache")
                post['timestamp'] = result['timestamp'].replace(
                    tzinfo=pytz.utc)
                logger.debug(f"timestamp from DB: {post['timestamp']}")
            else:
                # This fires when we have a newly published post
                logger.debug(f"did not find post timestamp {post['slug']}: ")
                collection.insert({
                    '_id': post['slug'],
                    'timestamp': utcnow,
                })
                post['timestamp'] = utcnow.replace(tzinfo=pytz.utc)
        else:
            post['timestamp'] = utcnow.replace(tzinfo=pytz.utc)

    return posts


def split_posts(doc):
    """
    split the raw document into an array of raw posts
    """
    logger.debug('--split_posts start--')
    status = None
    raw_posts = []
    raw_post_contents = []
    ignore_orphan_text = True

    if hr := doc.soup.hr:
        if hr.find("p", text=end_liveblog_regex):
            status = 'after'
            # Get rid of everything after the Horizontal Rule
        hr.extract()

    body = doc.soup.body
    for child in body.children:
        if is_post_marker(child):
            # Detected first post stop ignoring orphan text
            if ignore_orphan_text:
                ignore_orphan_text = False
        elif ignore_orphan_text:
            continue
        elif is_post_end_marker(child):
            ignore_orphan_text = True
            raw_posts.append(raw_post_contents)
            raw_post_contents = []
        else:
            raw_post_contents.append(child)
    return status, raw_posts


def getAuthorsData():
    """
    Transforms the authors excel file
    into a format like this
    "dm": {
        "initials": "dm",
        "name": "Domenico Montanaro",
        "role": "NPR Political Editor & Digital Audience",
        "page": "http://www.npr.org/people/xxxx",
        "img": "http://media.npr.org/assets/img/yyy.jpg"
    }
    """
    authors = {}
    try:
        book = xlrd.open_workbook(app_config.AUTHORS_PATH)
        sheet = book.sheet_by_index(0)
        header = True
        for row in sheet.get_rows():
            # Ignore header row
            if header:
                header = False
                continue
            initials = row[0].value
            if initials in authors:
                logger.warning("Duplicate initials on authors dict: %s" % (
                               initials))
                continue
            author = {}
            author['initials'] = row[0].value
            author['name'] = row[1].value
            author['role'] = row[2].value
            author['page'] = row[3].value
            author['img'] = row[4].value
            authors[initials] = author
    except Exception, e:
        logger.error("Could not process the authors excel file: %s" % (e))
    finally:
        return authors


def parse(doc, authors=None):
    """
    Custom parser for the debates google doc format
    returns boolean marking if the transcript is live or has ended
    """
    try:
        parsed_document = {}
        status = None
        pinned_post = None
        logger.info('-------------start------------')
        if not authors:
            authors = getAuthorsData()
        status, raw_posts = split_posts(doc)
        posts = parse_raw_posts(raw_posts, authors)
        if posts:
            idx = find_pinned_post(posts)
            if idx is not None:
                pinned_post = posts.pop(idx)
                pinned_post = compose_pinned_post(pinned_post)
            else:
                logger.error("Did not find a pinned post on the document")
            ordered_posts = order_posts(posts)
            published_posts = filter(lambda p: p['published'] == 'yes',
                                     ordered_posts)
            pinned_post['timestamp'] = add_last_timestamp(published_posts)
            logger.info('Number of published posts %s' % len(published_posts))
            logger.info('Total number of Posts: %s' % len(ordered_posts))
            if not status and len(published_posts):
                status = 'during'
            elif not status:
                status = 'before'
        else:
            # Handle empty initial liveblog
            logger.warning('Have not found posts.')
            status = 'before'
            ordered_posts = []
        parsed_document['status'] = status
        parsed_document['pinned_post'] = pinned_post
        parsed_document['posts'] = ordered_posts
        logger.info('storing liveblog backup')
        with open(app_config.LIVEBLOG_BACKUP_PATH, 'wb') as f:
            pickle.dump(parsed_document, f)
    except Exception, e:
        logger.error('unexpected exception: %s' % e)
        logger.info('restoring liveblog backup and setting error status')
        with open(app_config.LIVEBLOG_BACKUP_PATH, 'rb') as f:
            parsed_document = pickle.load(f)
            parsed_document['status'] = 'error'
    finally:
        logger.info('-------------end------------')
    return parsed_document
