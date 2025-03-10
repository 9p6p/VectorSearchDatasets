# Copyright (c) 2024 Intel Corporation
# SPDX-License-Identifier: MIT

# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

# Original Facebook LICENSE file:
# https://github.com/facebookresearch/KILT/blob/2664322b9a994be686e4c3a9e8f75a0b70927f22/LICENSE

import multiprocessing
from multiprocessing.pool import ThreadPool
import sys
import argparse
import pickle
import json
import os
import spacy
from tqdm import tqdm, trange
from tqdm.contrib.concurrent import process_map

import kilt.kilt_utils as utils
from kilt.knowledge_source import KnowledgeSource


def create_chunk(document, buffer, paragraph_id, paragraph, section, prepend_section):
    start = buffer[0].idx
    end = buffer[-1].idx + len(buffer[-1])

    anchors = [
        {
            "text": anchor["text"],
            "href": anchor["href"],
            "source": {
                "paragraph_id": anchor["paragraph_id"],
                "start": anchor["start"],
                "end": anchor["end"],
            },
            "start": anchor["start"] - start,
            "end": anchor["end"] - start,
        }
        for anchor in document["anchors"]
        if anchor["paragraph_id"] == paragraph_id
        and anchor["start"] >= start
        and anchor["end"] <= end
    ]
    par_text = paragraph.text[start : end + 1].strip()
    if prepend_section:
        par_text = f"{section} {par_text}"
    n_words = len(par_text.split())

    return {
        "_id": document["_id"],
        "wikipedia_id": document["wikipedia_id"],
        "wikipedia_title": document["wikipedia_title"],
        "text": par_text,  #paragraph.text[start : end + 1].strip(),
        "tmp_len": n_words,  #len(buffer),
        "anchors": anchors,
        "categories": document["categories"],
        "history": document["history"],
        "sources": [{"paragraph_id": paragraph_id, "start": start, "end": end,}],
        "section": section,
    }


def run_thread(args):
    documents = args["documents"]
    nlp = args["nlp"]
    id = args["id"]
    rank = args["rank"]
    chunk_size = args["chunk_size"]

    #iter_ = tqdm(documents)
    #if id == 0 and rank == 0:
    #    iter_ = tqdm(documents)
    #else:
    iter_ = documents

    # initialization
    output = []

    for document in iter_:

        # initialization
        prepend_section = False
        buffer_words, buffer_toks = [], []
        nwords_buffer = 0
        section = "Section::::Abstract"

        # loop paragrpahs removing first (title)
        for paragraph_id, paragraph in enumerate(nlp.pipe(document["text"][1:]), 1):

            # if section then save name and move on
            if "Section::::" in paragraph.text:
                section = paragraph.text.strip()
                continue
            # if the paragraph begins with a bullet point, prepend the section title to the text as well.
            if paragraph.text[:10] == "BULLET::::":
                buffer_words += section.split()
                prepend_section = True

            for sentence in paragraph.sents:
                sent_words = sentence.text.split()
                if buffer_toks and len(buffer_words) + len(sent_words) >= chunk_size:
                    # create new chunk
                    new_chunk = create_chunk(
                        document, buffer_toks,
                        paragraph_id, paragraph, section, prepend_section
                    )
                    output.append(new_chunk)
                    buffer_words, buffer_toks = [], []
                    prepend_section = False

                # Use number of words, not number of tokens
                buffer_words += sent_words
                for token in sentence:
                    word = token.text.strip()
                    if word and len(word) > 0:
                        buffer_toks.append(token)

            if buffer_words:
                # create new chunk
                new_chunk = create_chunk(
                    document, buffer_toks,
                    paragraph_id, paragraph, section, prepend_section
                )

                # conditions on merging with previous chunk
                if (
                    output
                    and document["wikipedia_id"] == output[-1]["wikipedia_id"]
                    and section == output[-1]["section"]
                    and len(buffer_words) + output[-1]["tmp_len"] < chunk_size
                ):

                    # adjusting anchors offsets
                    for anchor in new_chunk["anchors"]:
                        anchor["start"] += len(output[-1]["text"]) + 1
                        anchor["end"] += len(output[-1]["text"]) + 1

                    # remove redundant section title preprended to current chunk
                    if prepend_section:
                        new_chunk["text"] = new_chunk["text"][len(section):]
                    # appending new data
                    output[-1]["text"] += " " + new_chunk["text"]
                    output[-1]["anchors"] += new_chunk["anchors"]
                    output[-1]["sources"] += new_chunk["sources"]
                    output[-1]["tmp_len"] += new_chunk["tmp_len"] #+ 1
                else:
                    output.append(new_chunk)
                buffer_words, buffer_toks = [], []
                prepend_section = False

    for out in output:
        del out["tmp_len"]

    return output


def store_chunks(documents, num_threads, folder):
    for id, chunk in enumerate(utils.chunk_it(documents, num_threads)):
        out_filename = os.path.join(folder, "documents_{}.p".format(id))
        pickle.dump(chunk, open(out_filename, "wb"))


def load_chunk(id, folder):
    in_filename = os.path.join(folder, "documents_{}.p".format(id))
    return pickle.load(open(in_filename, "rb"))


def load_all_documents_from_ks(cursor, steps, n):
    documents = []
    j = 0
    for document in cursor:
        if j % steps == 0:
            sys.stdout.write("{}/{} \r".format(j, n))
            sys.stdout.flush()
        documents.append(document)
        j += 1
    return documents


def preprocess_data(num_threads, folder):

    ks = KnowledgeSource()
    n = ks.get_num_pages()
    steps = int(n / 100)

    cursor = ks.get_all_pages_cursor()

    print("LOADING ALL DOCUMENTS", flush=True)
    ducuments = load_all_documents_from_ks(cursor, steps, n)
    store_chunks(ducuments, num_threads, folder)


def main(rank, num_threads, folder, chunk_size):

    print("loading chunk {}".format(rank), flush=True)
    documents = load_chunk(rank, folder)

    arguments = [
        {
            "rank": rank,
            "id": id,
            "documents": chunk,
            "nlp": spacy.load("en_core_web_sm"),
            "chunk_size": chunk_size,
        }
        for id, chunk in enumerate(utils.chunk_it(documents, num_threads))
    ]

    #print("starting {} threads in {}".format(num_threads, rank))
    #pool = ThreadPool(num_threads)
    #results = pool.map(run_thread, arguments)
    results = process_map(run_thread, arguments, max_workers=num_threads)

    f = open(os.path.join(folder, "kilt_{}.jsonl".format(rank)), "w+",)

    i = 1
    for output in results:
        for msg in output:
            f.write("{}\t{}\n".format(i, json.dumps(msg)))
            i += 1
    f.close()
    #pool.terminate()
    #pool.join()
    print("done {}".format(rank))


def merge_files(num_threads, folder):

    f = open(os.path.join(folder, "kilt.jsonl"), "w+")
    i = 1
    for rank in trange(num_threads):
        filename = os.path.join(folder, "kilt_{}.jsonl".format(rank))
        print("reading {}".format(filename), flush=True)
        with open(filename, "r") as fin:
            lines = fin.readlines()
            for line in tqdm(lines):
                elements = line.split("\t")
                if len(elements) != 2:
                    print(
                        "ERROR: len(elements)!=2 -> {}".format(len(elements)),
                        flush=True,
                    )
                else:
                    #f.write("{}\t{}\n".format(i, elements[1].strip()))
                    f.write("{}\n".format(elements[1].strip()))
                    i += 1
    f.close()
    print("done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--step",
        type=str,
        choices=["preprocess", "main", "merge"],
        help="step to exectue",
    )

    parser.add_argument(
        "--chunk_size", default=100, type=int, help="chunk max token size",
    )

    parser.add_argument(
        "--folder", type=str, help="path where to save and load files",
    )

    parser.add_argument(
        "--rank", default=None, type=int, help="rank in a distributed execution",
    )

    parser.add_argument(
        "--threads", default=None, type=int, help="number of threads",
    )

    args = parser.parse_args()

    if args.threads == None:
        args.threads = int(multiprocessing.cpu_count())

    # step 1
    if args.step == "preprocess":
        preprocess_data(num_threads=args.threads, folder=args.folder)
    # step 2
    elif args.step == "main":
        main(
            rank=args.rank,
            num_threads=args.threads,
            folder=args.folder,
            chunk_size=args.chunk_size,
        )
    # step 3
    elif args.step == "merge":
        merge_files(num_threads=args.threads, folder=args.folder)
