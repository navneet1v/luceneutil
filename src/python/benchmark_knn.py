#!/usr/bin/env python3

"""
minimal knn benchmark runner: baseline (lucene 10.3) vs candidate branch

usage:
  python benchmark_knn.py --candidate-branch <branch> [options]

examples:
  # basic run
  python benchmark_knn.py --candidate-branch my-feature

  # reuse indexed data for multiple query runs
  python benchmark_knn.py --candidate-branch my-feature --reuse-index --query-runs 5

  # custom parameters
  python benchmark_knn.py --candidate-branch my-feature --ndoc 1000000 --max-conn 32
"""

import argparse
import os
import subprocess
from pathlib import Path

import constants

BASELINE_BRANCH = "main"
BASELINE_VERSION = "11.0.0"

def run_cmd(cmd, cwd=None):
    """run command and check for errors."""
    print(f"running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=cwd)

def setup_checkout(path, branch_or_tag, repo='apache', force=False):
    """setup lucene checkout."""
    if not os.path.exists(path):
        print(f"cloning lucene to {path}...")
        run_cmd(['git', 'clone', f'https://github.com/{repo}/lucene.git', path])
        force = True

    if force:
        print(f"checking out {branch_or_tag}...")
        run_cmd(['git', 'fetch', 'origin'], cwd=path)
        run_cmd(['git', 'checkout', branch_or_tag], cwd=path)

        print(f"building {path}...")
        run_cmd(['./gradlew', 'jar'], cwd=path)
    else:
        print(f"using existing checkout at {path}")

def update_gradle_props(lucene_path):
    """update gradle.properties to point to lucene checkout."""
    props_file = Path(constants.BENCH_BASE_DIR) / 'gradle.properties'
    if props_file.exists():
        content = props_file.read_text()
        lines = []
        for line in content.split('\n'):
            if line.startswith('external.lucene.repo='):
                lines.append(f'external.lucene.repo={lucene_path}')
            elif line.startswith("lucene.version="):
              lines.append(f'lucene.version={BASELINE_VERSION}')
            else:
                lines.append(line)
        props_file.write_text('\n'.join(lines))
    else:
        props_file.write_text(f'\nexternal.lucene.repo={lucene_path}\nlucene.version={BASELINE_VERSION}\n')

def run_benchmark(lucene_path, name, args, reuse_index):
    """run knn benchmark."""
    print(f"\n{'='*60}")
    print(f"running: {name}")
    print(f"{'='*60}\n")

    update_gradle_props(lucene_path)

    # build luceneutil
    run_cmd(['./gradlew', 'compileKnn'], cwd=constants.BENCH_BASE_DIR)

    # build command
    cp = ':'.join([
        f'{lucene_path}/lucene/core/build/libs/lucene-core-*.jar',
        f'{constants.BENCH_BASE_DIR}/build',
    ])

    cmd = [
        constants.JAVA_EXE,
        '-cp', cp,
        '--add-modules', 'jdk.incubator.vector',
        '--enable-native-access=ALL-UNNAMED',
        'knn.KnnGraphTester',
        '-dim', str(args.dim),
        '-docs', args.doc_vectors,
        '-ndoc', str(args.ndoc),
        '-maxConn', str(args.max_conn),
        '-beamWidthIndex', str(args.beam_width),
        '-fanout', str(args.fanout),
        '-topK', str(args.topk),
        '-numIndexThreads', str(args.index_threads),
        '-numMergeThread', str(args.merge_threads),
        '-numMergeWorker', str(args.merge_workers),
        '-metric', args.metric,
    ]

    if reuse_index:
        cmd.append('-search-and-stats')
    else:
        cmd.append('-reindex')
        cmd.append('-search-and-stats')

    cmd.append(args.query_vectors)

    if args.quantize_bits != 32:
        cmd.extend(['-quantize', '-quantizeBits', str(args.quantize_bits)])
        if args.quantize_bits <= 4:
            cmd.append('-quantizeCompress')

    if args.force_merge:
        cmd.append('-forceMerge')

    # run benchmark
    log_file = f"{constants.LOGS_DIR}/{name}.log"
    print(f"logging to: {log_file}")

    with open(log_file, 'w') as f:
        subprocess.check_call(cmd, stdout=f, stderr=subprocess.STDOUT)

    # print summary
    with open(log_file) as f:
        for line in f:
            if line.startswith('SUMMARY:'):
                print(f"\n{name} results:")
                print(line.strip())
                return line.strip()

def main():
    parser = argparse.ArgumentParser(description='run knn benchmarks: baseline vs candidate')

    # required
    parser.add_argument('--candidate-branch', required=True, help='candidate branch name')

    # paths
    parser.add_argument('--baseline-path', default=f"{constants.BASE_DIR}/lucene_baseline")
    parser.add_argument('--candidate-path', default=f"{constants.BASE_DIR}/lucene_candidate")

    # dataset
    parser.add_argument('--doc-vectors', default='/lucenedata/enwiki/cohere-v3/cohere-v3-wikipedia-en-scattered-1024d.docs.vec')
    parser.add_argument('--query-vectors', default='/lucenedata/enwiki/cohere-v3/cohere-v3-wikipedia-en-scattered-1024d.queries.vec')
    parser.add_argument('--dim', type=int, default=1024)

    # benchmark params
    parser.add_argument('--ndoc', type=int, default=400000)
    parser.add_argument('--max-conn', type=int, default=16)
    parser.add_argument('--beam-width', type=int, default=100)
    parser.add_argument('--fanout', type=int, default=100)
    parser.add_argument('--topk', type=int, default=100)
    parser.add_argument('--quantize-bits', type=int, default=32, choices=[4, 7, 8, 32])
    parser.add_argument('--metric', default='cosine', choices=['cosine', 'dotproduct', 'mip'])
    parser.add_argument('--index-threads', type=int, default=8)
    parser.add_argument('--merge-threads', type=int, default=8)
    parser.add_argument('--merge-workers', type=int, default=24)
    parser.add_argument('--force-merge', action='store_true')

    # execution
    parser.add_argument('--reuse-index', action='store_true', help='reuse indexed data (skip reindexing)')
    parser.add_argument('--query-runs', type=int, default=1, help='number of query runs on same index')
    parser.add_argument('--checkout-baseline', action='store_true', help='checkout and build baseline')
    parser.add_argument('--checkout-candidate', action='store_true', help='checkout and build candidate')

    args = parser.parse_args()

    os.makedirs(constants.LOGS_DIR, exist_ok=True)

    # setup checkouts
    setup_checkout(args.baseline_path, f'{BASELINE_BRANCH}', force=args.checkout_baseline)
    setup_checkout(args.candidate_path, args.candidate_branch, 'navneet1v', force=args.checkout_candidate)

    # run baseline
    print("\n" + "="*60)
    print(f"baseline: lucene {BASELINE_BRANCH}")
    print("="*60)
    baseline_result = run_benchmark(args.baseline_path, 'baseline', args, False)

    # additional query runs on baseline index
    for i in range(1, args.query_runs):
        print(f"\nbaseline query run {i+1}/{args.query_runs}")
        run_benchmark(args.baseline_path, f'baseline_run{i+1}', args, True)

    # run candidate
    print("\n" + "="*60)
    print(f"candidate: {args.candidate_branch}")
    print("="*60)
    candidate_result = run_benchmark(args.candidate_path, 'candidate', args, False)

    # additional query runs on candidate index
    for i in range(1, args.query_runs):
        print(f"\ncandidate query run {i+1}/{args.query_runs}")
        run_benchmark(args.candidate_path, f'candidate_run{i+1}', args, True)

    # compare
    print("\n" + "="*60)
    print("comparison")
    print("="*60)
    print(f"baseline:  {baseline_result}")
    print(f"candidate: {candidate_result}")
    print(f"\nlogs: {constants.LOGS_DIR}/")

if __name__ == '__main__':
    main()
