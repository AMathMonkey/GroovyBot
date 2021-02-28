import sqlite3 as sql

conn = sql.connect("groovy.db")
conn.row_factory = sql.Row


class QUERIES:
    create_runs = """
        CREATE TABLE IF NOT EXISTS runs (
            name TEXT,
            category TEXT,
            level TEXT,
            time TEXT,
            date TEXT,
            place INTEGER,
            PRIMARY KEY (name, category, level, time, date)
        );
    """

    create_scores = """
        CREATE TABLE IF NOT EXISTS scores (
            name TEXT PRIMARY KEY,
            score INTEGER
        );
    """

    create_files = """
        CREATE TABLE IF NOT EXISTS files (
            filename TEXT PRIMARY KEY,
            data BLOB
        );
    """

    get_one_run_for_ilranking = """
        SELECT * FROM runs 
            WHERE category = ?
            AND level = ?
            AND lower(name) = ?
    """

    get_one_run_for_new_runs = """
        SELECT * from runs
            WHERE level = :level
            AND category = :category
            AND time = :time
            AND name = :name
            AND date = :date
    """

    insert_run = """
        INSERT INTO runs (name, category, level, time, date, place)
            VALUES (:name, :category, :level, :time, :date, :place)
    """

    insert_score = """
        INSERT INTO scores (name, score)
            VALUES (?, ?)
    """

    get_wr_runs = "SELECT * FROM runs WHERE place = 1"

    get_point_rankings = "SELECT data FROM files WHERE filename = 'PointRankings'"

    replace_point_rankings = (
        "REPLACE INTO files (filename, data) VALUES ('PointRankings', ?)"
    )

    delete_all_runs = "DELETE FROM runs"

    delete_all_scores = "DELETE FROM scores"


c = conn.cursor()
c.execute(QUERIES.create_runs)
c.execute(QUERIES.create_scores)
c.execute(QUERIES.create_files)
conn.commit()