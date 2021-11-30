import multiprocessing
import os
import sys
import traceback
from itertools import groupby
from time import time
from typing import Dict, List, Set, Tuple

import dejavu.logic.decoder as decoder
from dejavu.base_classes.base_database import get_database
from dejavu.config.settings import (DEFAULT_FS, DEFAULT_OVERLAP_RATIO,
                                    DEFAULT_WINDOW_SIZE, FIELD_FILE_SHA1,
                                    FIELD_TOTAL_HASHES,
                                    FINGERPRINTED_CONFIDENCE,
                                    FINGERPRINTED_HASHES, HASHES_MATCHED,
                                    INPUT_CONFIDENCE, INPUT_HASHES, OFFSET,
                                    OFFSET_SECS, SONG_ID, SONG_NAME, SONG_SINGER, SONG_ALBUM, SONG_LENGTH,
                                    SONG_PUBLISHER, SONG_PUBLICTIME, SONGS_TABLENAME, TOPN)
from dejavu.logic.fingerprint import fingerprint
from dejavu.logic.information import information
from dejavu.third_party.dejavu_timer import DejavuTimer


class Dejavu:
    def __init__(self, config):
        self.config = config

        # initialize db
        db_cls = get_database(config.get("database_type", "mysql").lower())

        self.db = db_cls(**config.get("database", {}))

        # if we should limit seconds fingerprinted,
        # None|-1 means use entire track
        self.limit = self.config.get("fingerprint_limit", None)
        if self.limit == -1:  # for JSON compatibility
            self.limit = None

    def setup(self) -> None:
        self.db.setup()

    @DejavuTimer(name=__name__ + ".__load_fingerprinted_audio_hashes()\t\t\t\t")
    def __load_fingerprinted_audio_hashes(self) -> Set[str]:
        """
        Keeps a dictionary with the hashes of the fingerprinted songs, in that way is possible to check
        whether or not an audio file was already processed.
        """
        # get songs previously indexed
        self.songs = self.db.get_songs()
        songhashes_set = set()  # to know which ones we've computed before
        for song in self.songs:
            song_hash = song[FIELD_FILE_SHA1]
            songhashes_set.add(song_hash)
        return songhashes_set

    def get_fingerprinted_songs(self) -> List[Dict[str, any]]:
        """
        To pull all fingerprinted songs from the database.

        :return: a list of fingerprinted audios from the database.
        """
        return self.db.get_songs()

    def delete_songs_by_id(self, song_ids: List[int]) -> None:
        """
        Deletes all audios given their ids.

        :param song_ids: song ids to delete from the database.
        """
        self.db.delete_songs_by_id(song_ids)

    def fingerprint_directory(self, path: str, extensions: str, nprocesses: int = None) -> None:
        """
        Given a directory and a set of extensions it fingerprints all files that match each extension specified.

        :param path: path to the directory.
        :param extensions: list of file extensions to consider.
        :param nprocesses: amount of processes to fingerprint the files within the directory.
        """
        # Try to use the maximum amount of processes if not given.
        try:
            nprocesses = nprocesses or multiprocessing.cpu_count()
        except NotImplementedError:
            nprocesses = 1
        else:
            nprocesses = 1 if nprocesses <= 0 else nprocesses

        pool = multiprocessing.Pool(nprocesses)

        songhashes_set = self.__load_fingerprinted_audio_hashes()
        filenames_to_fingerprint = []
        for filename, _ in decoder.find_files(path, extensions):
            # don't refingerprint already fingerprinted files
            if decoder.unique_hash(filename) in songhashes_set:
                print(f"{filename} already fingerprinted, continuing...")
                continue

            filenames_to_fingerprint.append(filename)

        # Prepare _fingerprint_worker input
        worker_input = list(zip(filenames_to_fingerprint, [self.limit] * len(filenames_to_fingerprint)))

        # Send off our tasks
        iterator = pool.imap_unordered(Dejavu._fingerprint_worker, worker_input)

        # Loop till we have all of them
        while True:
            try:
                song_name, hashes, file_hash, song_publisher, song_length, song_singer, song_album, song_public = next(
                    iterator)
            except multiprocessing.TimeoutError:
                continue
            except StopIteration:
                break
            except Exception:
                print("Failed fingerprinting")
                # Print traceback because we can't reraise it here
                traceback.print_exc(file=sys.stdout)
            else:
                sid = self.db.insert_song(song_name, file_hash, len(hashes), song_publisher, song_length, song_singer,
                                          song_album, song_public)

                self.db.insert_hashes(sid, hashes)
                self.db.set_song_fingerprinted(sid)
                self.__load_fingerprinted_audio_hashes()

        pool.close()
        pool.join()

    def fingerprint_file(self, file_path: str) -> None:
        """
        Given a path to a file the method generates hashes for it and stores them in the database
        for later be queried.

        :param file_path: path to the file.
        """
        song_hash = decoder.unique_hash(file_path)
        # don't refingerprint already fingerprinted files
        songhashes_set = self.__load_fingerprinted_audio_hashes()
        if song_hash in songhashes_set:
            print(f"{file_path} already fingerprinted, continuing...")
        else:
            song_name, hashes, file_hash, song_publisher, song_length, song_singer, song_album, song_public = Dejavu._fingerprint_worker(
                (file_path, self.limit))
            sid = self.db.insert_song(song_name, file_hash, len(hashes), song_publisher, song_length, song_singer,
                                      song_album, song_public)

            self.db.insert_hashes(sid, hashes)
            self.db.set_song_fingerprinted(sid)
            self.__load_fingerprinted_audio_hashes()

    def fingerprint_file_by_self(self, file_path: str, song_name: str, song_publisher: str = None,
                                 song_length: float = 0, song_singer: str = None, song_album: str = None,
                                 song_public: str = None) -> None:
        """
        Given a path to a file the method generates hashes for it and stores them in the database
        for later be queried.

        :param file_path: path to the file.
        :param song_name: The name of the song.
        :param song_publisher: The publisher of the song.
        :param song_length: The length of the song.
        :param song_singer: The singer of the song.
        :param song_album: The album of the song.
        :param song_public: The public time of the song.

        """
        song_hash = decoder.unique_hash(file_path)
        # don't refingerprint already fingerprinted files
        songhashes_set = self.__load_fingerprinted_audio_hashes()
        if song_hash in songhashes_set:
            print(f"{file_path} already fingerprinted, continuing...")
        else:
            hashes, file_hash = Dejavu._fingerprint_worker((file_path, self.limit), False)
            sid = self.db.insert_song(song_name, file_hash, len(hashes), song_publisher, song_length, song_singer,
                                      song_album, song_public)

            self.db.insert_hashes(sid, hashes)
            self.db.set_song_fingerprinted(sid)
            self.__load_fingerprinted_audio_hashes()

    @DejavuTimer(name=__name__ + ".generate_fingerprints()\t\t\t\t\t\t")
    def generate_fingerprints(self, samples: List[int], Fs=DEFAULT_FS) -> Tuple[List[Tuple[str, int]], float]:
        f"""
        Generate the fingerprints for the given sample data (channel).

        :param samples: list of ints which represents the channel info of the given audio file.
        :param Fs: sampling rate which defaults to {DEFAULT_FS}.
        :return: a list of tuples for hash and its corresponding offset, together with the generation time.
        """
        t = time()
        hashes = fingerprint(samples, Fs=Fs)
        fingerprint_time = time() - t
        return hashes, fingerprint_time

    @DejavuTimer(name=__name__ + ".find_matches()\t\t\t\t\t\t\t")
    def find_matches(self, hashes: List[Tuple[str, int]]) -> Tuple[List[Tuple[int, int]], Dict[str, int], float]:
        """
        Finds the corresponding matches on the fingerprinted audios for the given hashes.

        :param hashes: list of tuples for hashes and their corresponding offsets
        :return: a tuple containing the matches found against the db, a dictionary which counts the different
         hashes matched for each song (with the song id as key), and the time that the query took.

        """
        t = time()
        matches, dedup_hashes = self.db.return_matches(hashes)
        query_time = time() - t

        return matches, dedup_hashes, query_time

    @DejavuTimer(name=__name__ + ".align_matches()\t\t\t\t\t\t\t")
    def align_matches(self, matches: List[Tuple[int, int]], dedup_hashes: Dict[str, int], queried_hashes: int,
                      topn: int = TOPN) -> List[Dict[str, any]]:
        """
        Finds hash matches that align in time with other matches and finds
        consensus about which hashes are "true" signal from the audio.

        :param matches: matches from the database
        :param dedup_hashes: dictionary containing the hashes matched without duplicates for each song
        (key is the song id).
        :param queried_hashes: amount of hashes sent for matching against the db
        :param topn: number of results being returned back.
        :return: a list of dictionaries (based on topn) with match information.
        """
        # count offset occurrences per song and keep only the maximum ones.
        sorted_matches = sorted(matches, key=lambda m: (m[0], m[1]))
        counts = [(*key, len(list(group))) for key, group in groupby(sorted_matches, key=lambda m: (m[0], m[1]))]
        songs_matches = sorted(
            [max(list(group), key=lambda g: g[2]) for key, group in groupby(counts, key=lambda count: count[0])],
            key=lambda count: count[2], reverse=True
        )

        songs_result = []
        if len(songs_matches) == 0:
            return songs_result

        song_ids = [song_match[0] for song_match in songs_matches[0:topn]]
        songs = self.db.get_songs_by_ids(song_ids)
        songs_dict = {song[SONG_ID]: song for song in songs}

        for song_id, offset, _ in songs_matches[0:topn]:  # consider topn elements in the result
            song = songs_dict.get(song_id)

            song_name = song.get(SONG_NAME, None)
            song_hashes = song.get(FIELD_TOTAL_HASHES, None)
            song_publisher = song.get(SONG_PUBLISHER, None)
            song_length = song.get(SONG_LENGTH, None)
            song_singer = song.get(SONG_SINGER, None)
            song_album = song.get(SONG_ALBUM, None)
            song_public = song.get(SONG_PUBLICTIME, None)
            nseconds = round(float(offset) / DEFAULT_FS * DEFAULT_WINDOW_SIZE * DEFAULT_OVERLAP_RATIO, 5)
            hashes_matched = dedup_hashes[song_id]

            song = {
                SONG_ID: song_id,
                SONG_NAME: song_name,
                SONG_ALBUM: song_album,
                SONG_SINGER: song_singer,
                SONG_PUBLISHER: song_publisher,
                SONG_PUBLICTIME: song_public,
                SONG_LENGTH: song_length,
                INPUT_HASHES: queried_hashes,
                FINGERPRINTED_HASHES: song_hashes,
                HASHES_MATCHED: hashes_matched,
                # Percentage regarding hashes matched vs hashes from the input.
                INPUT_CONFIDENCE: round(hashes_matched / queried_hashes, 2),
                # Percentage regarding hashes matched vs hashes fingerprinted in the db.
                FINGERPRINTED_CONFIDENCE: round(hashes_matched / song_hashes, 2),
                OFFSET: offset,
                OFFSET_SECS: nseconds,
                FIELD_FILE_SHA1: song.get(FIELD_FILE_SHA1, None).encode("utf8")
            }

            songs_result.append(song)

        return songs_result

    @DejavuTimer(name=__name__ + ".recognize()\t\t\t\t\t\t\t")
    def recognize(self, recognizer, *options, **kwoptions) -> Dict[str, any]:
        r = recognizer(self)
        return r.recognize(*options, **kwoptions)

    @staticmethod
    def _fingerprint_worker(arguments, info=True):
        # Pool.imap sends arguments as tuples so we have to unpack
        # them ourself.
        try:
            file_name, limit = arguments
        except ValueError:
            pass

        fingerprints, file_hash = Dejavu.get_file_fingerprints(file_name, limit, print_output=True)

        if info:
            song_name, song_publisher, song_length, song_singer, song_album, song_public = information(file_name)
            return song_name, fingerprints, file_hash, song_publisher, song_length, song_singer, song_album, song_public

        return fingerprints, file_hash

    @staticmethod
    def get_file_fingerprints(file_name: str, limit: int, print_output: bool = False):
        channels, fs, file_hash = decoder.read(file_name, limit)
        fingerprints = set()
        channel_amount = len(channels)
        for channeln, channel in enumerate(channels, start=1):
            if print_output:
                print(f"Fingerprinting channel {channeln}/{channel_amount} for {file_name}")

            hashes = fingerprint(channel, Fs=fs)

            if print_output:
                print(f"Finished channel {channeln}/{channel_amount} for {file_name}")

            fingerprints |= set(hashes)

        return fingerprints, file_hash
