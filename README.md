## PROJECT NOT UNDER ACTIVE MANAGEMENT

This project will no longer be maintained by Intel.

Intel has ceased development and contributions including, but not limited to, maintenance, bug fixes, new releases, or updates, to this project.  

Intel no longer accepts patches to this project.

If you have an ongoing need to use this project, are interested in independently developing it, or would like to maintain patches for the open source software community, please create your own fork of this project.  

Contact: webadmin@linux.intel.com
# Vector Search Datasets

This repository provides code to generate several datasets for similarity search benchmarking and evaluation on 
high-dimensional vectors stemming from recent deep learning models. The available datasets are:

* [DPR](dpr/README.md) [[1]](#1)
* [open-images](openimages/README.md) [[2]](#2)
* [rqa](rqa/README.md) [[3]](#3)
* [wit](wit/README.md) [[3]](#3)
* [wikipedia](text/README.md)

Please see the details of each dataset in the respective README files.

## References

<a id="1">[1]</a>
Aguerrebere, C.; Bhati I.; Hildebrand M.; Tepper M.; Willke T.:Similarity search in the blink of an eye with compressed
indices. In: Proceedings of the VLDB Endowment, 16, 11, 3433 - 3446. (2023)

<a id="2">[2]</a>
Aguerrebere, C.; Hildebrand M.; Bhati I.; Willke T.; Tepper M..: Locally-adaptive Quantization for Streaming Vector
Search. (2024) [arxiv]

<a id="3">[3]</a>
Tepper M.; Bhati I.; Aguerrebere, C.; Hildebrand M.; Willke T.: LeanVec: Search your vectors faster by making them fit.
arXiv preprint arXiv:2312.16335 (2024)
