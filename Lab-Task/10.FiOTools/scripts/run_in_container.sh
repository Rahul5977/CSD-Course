#!/bin/sh
# Runs inside the csd-fio:lab10 container (Ubuntu 24.04 + fio from apt).
#   /lab      -> this lab folder (bind mount)
#   /fio-lab  -> dedicated Docker volume (ext4 on the VM's virtio disk); the ONLY write target
# Usage: run_in_container.sh main|supp|all
set -eu
MODE=${1:-all}
export ENGINE=${ENGINE:-libaio} SIZE=1g RUNTIME=${RUNTIME:-30} RAMP=${RAMP:-5}
export FIO_FILE=/fio-lab/db-test.bin
OUT=/lab/results
REPS=${REPS:-3}
CASES="A_randread_4k B_randrw70_4k C_randrw30_8k D_seqread_256k"

case "$FIO_FILE" in /fio-lab/*) ;; *) echo "refusing: target outside /fio-lab"; exit 1;; esac

env_capture() {
  {
    echo "date_utc: $(date -u +%FT%TZ)"
    echo "fio: $(fio --version)"
    echo "kernel: $(uname -r)  arch: $(uname -m)"
    grep PRETTY_NAME /etc/os-release
    echo "cpus_visible: $(nproc)"
    grep -E 'MemTotal|MemAvailable' /proc/meminfo
    echo "--- target filesystem"; df -hT /fio-lab | tail -1
    mount | grep ' /fio-lab '
    dev=$(basename "$(df /fio-lab | tail -1 | awk '{print $1}')" | sed 's/[0-9]*$//')
    echo "block_dev: $dev"
    for f in rotational scheduler nr_requests max_sectors_kb logical_block_size; do
      printf '%s: %s\n' "$f" "$(cat /sys/block/$dev/queue/$f 2>/dev/null)"; done
  } > "$OUT/environment.txt"
}

prep() {
  # Lay the 1 GiB file out once with real (non-zero) data so later reads hit allocated blocks.
  if [ ! -s "$FIO_FILE" ]; then
    fio --name=prep --filename="$FIO_FILE" --size=1g --rw=write --bs=1M --direct=1 \
        --ioengine=libaio --iodepth=8 --output=/dev/null
  fi
  ls -l "$FIO_FILE"
}

run() { # run <case> <qd> <outfile>
  QD=$2 fio "/lab/jobs/$1.fio" --output-format=json --output="$3"
  echo "$(date +%T) done $1 qd=$2 -> $(basename "$3")"
}

main() {
  for c in $CASES; do QD=1 fio --parse-only "/lab/jobs/$c.fio" >/dev/null; done
  echo "parse-only OK for all job files"
  # repetitions are the OUTER loop so slow drift spreads evenly across cases
  r=1; while [ $r -le $REPS ]; do
    for c in $CASES; do for qd in 1 8 32; do
      run "$c" "$qd" "$OUT/raw/${c}_qd${qd}_r${r}.json"
    done; done
    r=$((r+1))
  done
}

supp() {
  # S1: finer queue-depth sweep (where does scaling flatten?)
  for c in A_randread_4k D_seqread_256k; do for qd in 1 2 4 8 16 32 64 128; do
    RUNTIME=20 run "$c" "$qd" "$OUT/supp/sweep_${c}_qd${qd}.json"
  done; done
  s2; s3
}

s2() {
  # S2: engine cross-check at the deepest required queue. Docker's default seccomp
  # profile blocks io_uring_setup (EPERM), so a failure is logged, not fatal.
  f="$OUT/supp/engine_iouring_A_qd32.json"
  ENGINE=io_uring run A_randread_4k 32 "$f" || true
  # fio can exit 0 while the job itself failed, so check the JSON error field
  if grep -q '"error" : [1-9]' "$f"; then
    mv "$f" "${f%.json}.error.txt"
    echo "$(date +%T) io_uring unavailable in this container (EPERM, blocked by seccomp) - skipped"
  fi
}

s3() {
  # S3: cache sensitivity - 8 GiB working set (larger than the 8 GiB VM's RAM)
  FIO_FILE=/fio-lab/db-test-8g.bin SIZE=8g run A_randread_4k 1  "$OUT/supp/size8g_A_qd1.json"
  FIO_FILE=/fio-lab/db-test-8g.bin SIZE=8g run A_randread_4k 32 "$OUT/supp/size8g_A_qd32.json"
  rm -f /fio-lab/db-test-8g.bin
}

s4() {
  # S4: the full required matrix once more on an 8 GiB file (working set > VM RAM and
  # half of host RAM) to show how much of the 1 GiB result was host-cache effect
  for c in $CASES; do for qd in 1 8 32; do
    FIO_FILE=/fio-lab/db-test-8g.bin SIZE=8g run "$c" "$qd" "$OUT/supp/big8g_${c}_qd${qd}.json"
  done; done
  rm -f /fio-lab/db-test-8g.bin
}

wal() {
  # Case E (extension): WAL-style sync appends, 3 reps, file removed afterwards
  export FIO_FILE_WAL=/fio-lab/wal-test.bin
  fio --parse-only /lab/jobs/E_wal_8k_fdatasync.fio >/dev/null
  r=1; while [ $r -le $REPS ]; do
    RUNTIME=20 fio /lab/jobs/E_wal_8k_fdatasync.fio --output-format=json --output="$OUT/supp/E_wal_r$r.json"
    echo "$(date +%T) done E_wal rep $r"; r=$((r+1))
  done
  rm -f "$FIO_FILE_WAL"
}

env_capture; prep
case "$MODE" in main) main;; supp) supp;; wal) wal;; rest) s2; s3; wal;; big) s4;; all) main; supp; s4; wal;; esac
echo "ALL DONE"
