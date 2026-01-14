# KNN Benchmark Script

simple script to benchmark lucene 10.3 (baseline) vs candidate branch for knn performance.

## usage

### Pre-req
### Setting up luceneutil

First, pick a root directory, under which luceneutil will be checked out,
datasets exist, indices are built, Lucene source code is checked out,
etc.. We'll refer to this directory as `$LUCENE_BENCH_HOME` here.

```bash
# 1. checkout luceneutil:
# Choose a suitable directory, e.g. ~/Projects/lucene/benchmarks.

mkdir $LUCENE_BENCH_HOME && cd $LUCENE_BENCH_HOME
git clone https://github.com/mikemccand/luceneutil.git util

# 2. Run the initial setup script
cd util
python src/python/initial_setup.py

# you can run with -h option for help
python src/python/initial_setup.py -h
curl -s "https://get.sdkman.io" | bash

source "$HOME/.sdkman/bin/sdkman-init.sh"

sdk version
# install jdk 21 or 25: 25.0.1-tem
sdk install java 25.0.1-tem
# use JDK21 for lucene 10.3
sdk install java 21.0.9-tem
# this will set JAVA_HOME
sdk use java 21.0.9-tem

```

```bash
# basic 
cd src/python
python benchmark_knn.py --candidate-branch branch_10_3

# reuse indexed data for multiple query runs
python benchmark_knn.py --candidate-branch my-feature --reuse-index --query-runs 5

# custom parameters
python benchmark_knn.py --candidate-branch my-feature \
  --ndoc 1000000 \
  --max-conn 32 \
  --beam-width 100 \
  --fanout 50
```

## key options

**required:**
- `--candidate-branch` - git branch for candidate

**dataset:**
- `--doc-vectors` - document vectors file (default: cohere v3 1024d)
- `--query-vectors` - query vectors file
- `--dim` - vector dimensions (default: 1024)
- `--ndoc` - number of docs to index (default: 400,000)

**hnsw parameters:**
- `--max-conn` - max connections (default: 64)
- `--beam-width` - indexing beam width (default: 250)
- `--fanout` - search fanout (default: 100)
- `--topk` - results to retrieve (default: 100)
- `--quantize-bits` - quantization: 4, 7, 8, or 32 (default: 32 = no quantization)
- `--metric` - distance metric: cosine, dotproduct, mip (default: cosine)
- `--force-merge` - force merge to single segment

**execution:**
- `--reuse-index` - skip reindexing, only run queries
- `--query-runs` - number of query runs on same index (default: 1)
- `--skip-setup` - skip git checkout/build

## how it works

1. clones/checks out baseline (lucene 10.3) and candidate
2. builds both lucene checkouts
3. runs baseline: indexes data + runs queries
4. runs candidate: indexes data + runs queries
5. compares results

with `--reuse-index`, it skips reindexing and only runs queries on existing index.

with `--query-runs N`, it runs queries N times on the same indexed data.

## examples

```bash
# quick test
python benchmark_knn.py --candidate-branch my-feature --ndoc 100000

# production test with multiple query runs
python benchmark_knn.py --candidate-branch my-feature \
  --ndoc 1000000 \
  --query-runs 5 \
  --force-merge

# test quantization
python benchmark_knn.py --candidate-branch my-feature --quantize-bits 4

# different dataset
python benchmark_knn.py --candidate-branch my-feature \
  --doc-vectors /path/to/docs.vec \
  --query-vectors /path/to/queries.vec \
  --dim 768
```

## output

results are logged to `$BASE_DIR/logs/`:
- `baseline.log` - baseline results
- `candidate.log` - candidate results
- `baseline_run2.log`, etc. - additional query runs

summary line shows: recall, latency, cpu, docs, topk, fanout, etc.
