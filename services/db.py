import sqlite3 
import os
from datetime import datetime

import tools.config as config
from tools.wikiparser import *
import tools.cfg_parsing_utils as cfg_parser

class Database():
    def __init__(self) -> 'Database':
        db_directory_path = os.path.expandvars(config.DB_DIRECTORY_PATH)
        db_file_path = db_directory_path + "/" + config.DB_FILE_NAME
        try:
            os.mkdir(db_directory_path)

        except FileExistsError:
            pass

        self.__db = sqlite3.connect(db_file_path)

        self.__db.isolation_level = None
        self.__db.execute("PRAGMA foreign_keys = ON") # currently unused
        self.__create_tables()

    def __create_tables(self) -> None:
        # TODO: add support for wiki pages and translations in addition to dictionary pages
        try:
            self.__db.execute("CREATE TABLE Pages (id INTEGER PRIMARY KEY, name TEXT UNIQUE, content TEXT, datetime DATETIME)")
            self.__db.execute("CREATE INDEX idx_name ON Pages (name)")

        except sqlite3.OperationalError:
            pass

        try:
            self.__db.execute("CREATE TABLE Searches (id INTEGER PRIMARY KEY, text TEXT, datetime DATETIME)")
        except sqlite3.OperationalError:
            pass

    def save_search(self, search:str) -> None:
        """Save a search to local database for later use.

        If DB_SAVE_SEARCHES is set to False in config, search is not saved.
        """
        if config.DB_SAVE_SEARCHES == False:
            return None

        self.__db.execute("INSERT INTO Searches (text, datetime) VALUES (?, DATETIME('now', 'localtime'))", [search])
    
    def get_saved_pages(self, limit:int=None) -> list[tuple]:
        """Get saved pages from local database.

        limit: maximum number of pages to fetch. If no limit given, returns all pages.

        returns a list  of tuples containing the page's id, name and datetime (of when the page was added to db). The list is in the same order in which the pages' first versions were added to db.
        returns None if no pages found.

        Pages are returned even if DB_SAVE_PAGES is set to False in config. 
        To delete saved searches, use clear_pages().
        """
        if limit == None:
            pages = self.__db.execute("SELECT P.id, P.name, P.datetime FROM Pages P ORDER BY P.id ASC").fetchall()
        elif limit <= 0:
            raise ValueError
        else:
            pages = self.__db.execute("SELECT P.id, S.name FROM Pages P ORDER BY P.id DESC LIMIT ?", [limit]).fetchall()

        if pages == None:
            return None

        return pages

    def get_saved_searches(self, limit:int=None) -> list[tuple]:
        """Get saved searches from local database.

        limit: maximum number of searches to fetch. If no limit given, returns all searches.

        returns a list of tuples with id, text and datetime in ascending order (from oldest to newest).
        returns None if no searches found.

        Searches are returned even if DB_SAVE_SEARCHES is set to False in config. 
        To delete saved searches, use clear_searches().
        """
        if limit == None:
            searches = self.__db.execute("SELECT S.id, S.text, S.datetime FROM Searches S ORDER BY S.id ASC").fetchall()
        elif limit <= 0:
            raise ValueError
        else:
            searches = self.__db.execute("SELECT S.id, S.text, S.datetime FROM Searches S ORDER BY S.id DESC LIMIT ?", [limit]).fetchall()

        if searches == None:
            return None

        return searches


    def clear_searches(self) -> None:
        """ Remove all searches from database.
        """
        self.__db.execute("DELETE FROM Searches")
        return

    def clear_saved_pages(self) -> None: 
        """ Remove all pages from database.
        """
        self.__db.execute("DELETE FROM Searches")
        return

    def save_page(self, page:WikiParser) -> None:
        """Save a wikipage to local database for later use.

        If DB_SAVE_PAGES is set to False in config, page is not saved.
        """
        if config.DB_SAVE_PAGES == False:
            return None

        page_name = page.page_title
        page_content = page.page_text

        try:
            self.__db.execute("INSERT INTO Pages (name, content, datetime) VALUES (?, ?, DATETIME('now', 'localtime'))", [page_name, page_content])

        except sqlite3.IntegrityError: # update page if it's already saved
            self.__db.execute("UPDATE Pages SET content = ?, datetime = DATETIME('now', 'localtime') WHERE name = ?", [page_content, page_name])

    def page_needs_update(self, date:datetime) -> bool:
        expiration_time = cfg_parser.expiration_time_to_seconds(config.DB_PAGE_EXPIRATION_TIME)
        cur_page_archival_time = (datetime.now() - date).seconds

        if cur_page_archival_time > expiration_time:
            return True

        else:
            return False


    def load_page(self, page_name:str) -> WikiParser | None:
        """Load a wikipage from local database.

        Returns None if:
        - the requested page doesn't exist in database 
        - the requested page's addition datetime exceeds the DB_PAGE_EXPIRATION_TIME defined in config 
        - DB_USE_SAVED_PAGES is set to False in config

        Page name matching is case sensitive.
        """
        if config.DB_USE_SAVED_PAGES == False:
            return None

        page = self.__db.execute("SELECT P.name, P.content, P.datetime FROM Pages P WHERE p.name = ?", [page_name]).fetchone()
        if page == None:
            return None

        name, content, date = page[0], page[1], datetime.fromisoformat(page[2])

        if  self.page_needs_update(date):
            return None
        else:
            return WikiParser(content, name)