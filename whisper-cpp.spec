# whisper.cpp on the system ggml package (libggml + dlopen backends).
# Do not compile bundled ggml: backends (CPU ISA variants, Vulkan, OpenCL,
# HIP/ROCm) live in ggml / ggml-backend-*.

# Out-of-tree cmake/ninja can leave empty debugsourcefiles.list; rpm then
# fails on x86_64/aarch64. Keep -debuginfo; skip empty -debugsource.
%undefine _debugsource_packages

%bcond_without examples
%if %{with examples}
%global build_examples ON
%else
%global build_examples OFF
%endif

%bcond_with test
%if %{with test}
%global build_test ON
%else
%global build_test OFF
%endif

%bcond_with check

Summary:		Speech recognition in C/C++ (whisper.cpp)
Name:			whisper-cpp
Version:		1.9.2
Release:		1
License:		MIT
Group:			Sciences/Other
URL:			https://github.com/ggml-org/whisper.cpp
Source0:		https://github.com/ggml-org/whisper.cpp/archive/refs/tags/v%{version}/whisper.cpp-%{version}.tar.gz

# Prefer -O3 over distro -Os for the inference hot path
%global optflags %{optflags} -O3

BuildRequires:	cmake(ggml)
BuildRequires:	git-core
%if %{with examples}
# WHISPER_COMMON_FFMPEG: decode mp3/flac/… in the CLI (not just wav)
BuildRequires:	pkgconfig(libavformat)
BuildRequires:	pkgconfig(libavcodec)
BuildRequires:	pkgconfig(libavutil)
BuildRequires:	pkgconfig(libswresample)
%endif

Requires:	%{mklibname ggml}%{?_isa} >= 0.19.0
# Runtime backends are dlopen'd from ggml; recommend the useful ones.
Recommends:	ggml-backend-blas%{?_isa}
Recommends:	ggml-backend-vulkan%{?_isa}
Suggests:	ggml-backend-opencl%{?_isa}
Suggests:	ggml-backend-hip%{?_isa}

# ggml-config.cmake lists optional backends (CUDA, DNNL, …) as hard deps
%global __requires_exclude cmake\\((hip|roc|mkl|intelsycl|cudatoolkit|CUDAToolkit|dnnl|DNNL|openvino|OpenVINO|sycl|SYCL).*

BuildSystem:	cmake
BuildOption:	-DCMAKE_C_COMPILER=clang
BuildOption:	-DCMAKE_CXX_COMPILER=clang++
BuildOption:	-DBUILD_SHARED_LIBS:BOOL=ON
BuildOption:	-DWHISPER_USE_SYSTEM_GGML:BOOL=ON
BuildOption:	-DWHISPER_BUILD_EXAMPLES=%{build_examples}
# WHISPER_BUILD_SERVER is currently unused as a gate (server is part of
# examples), but keep it in sync so a future upstream split still works.
BuildOption:	-DWHISPER_BUILD_SERVER=%{build_examples}
BuildOption:	-DWHISPER_BUILD_TESTS=%{build_test}
# SDL2 pulls in talk-llama, which vendors a full llama.cpp tree.
BuildOption:	-DWHISPER_SDL2:BOOL=OFF
# Option exists but is not wired up in 1.9.2 (no libcurl usage).
BuildOption:	-DWHISPER_CURL:BOOL=OFF
%if %{with examples}
BuildOption:	-DWHISPER_COMMON_FFMPEG:BOOL=ON
%endif

%description
whisper.cpp runs OpenAI Whisper (and NVIDIA Parakeet) speech-to-text
models. Tensor kernels come from the system ggml package; optional
accelerators are separate:

* ggml-backend-blas — OpenBLAS
* ggml-backend-vulkan — Vulkan
* ggml-backend-opencl — OpenCL
* ggml-backend-hip — AMD ROCm/HIP

CLI tools are in %{name}-examples, the HTTP server in %{name}-server.

%package devel
Summary:	Development files for %{name}
Group:		Development/C++
Requires:	%{name}%{?_isa} = %{EVRD}
Requires:	cmake(ggml)

%description devel
Headers, pkg-config and CMake package config for whisper.cpp
(libwhisper, libparakeet). Requires system ggml (cmake(ggml)).

%if %{with test}
%package test
Summary:	Tests for %{name}
Group:		Development/Other
Requires:	%{name}%{?_isa} = %{EVRD}

%description test
%{summary}
%endif

%if %{with examples}
%package server
Summary:	HTTP inference server for %{name}
Group:		Servers
Requires:	%{name}%{?_isa} = %{EVRD}
Recommends:	ffmpeg

%description server
HTTP server for whisper.cpp. WAV (or, with --convert and ffmpeg,
other audio) is posted to the model.

Config: %{_sysconfdir}/sysconfig/whisper-server
Unit:   whisper.service  (default 127.0.0.1:8081, not 8080, so it
        can run next to llama-server)

  systemctl enable --now whisper.service

Models from https://huggingface.co/ggerganov/whisper.cpp (ggml-*.bin).
If MODEL is unset, the unit picks the best readable file from
MODEL_ORDER in %{_sysconfdir}/sysconfig/whisper-server (large-v3
down to tiny), searching /srv/ai then
%{_datarootdir}/%{name}/models. Packaged whisper-cpp-model-*
RPMs land in the second directory. Override with MODEL=.

The unit hides /home; extra model trees need a drop-in
ReadOnlyPaths=-/other/models. /usr is already readable.

GPU offload uses whatever ggml backends are installed. Disable with
--no-gpu. Device index: --device N (or WHISPER_ARG_DEVICE).

To transcribe:

  curl http://127.0.0.1:8081/inference \
    -H "Content-Type: multipart/form-data" \
    -F file="@audio.wav" \
    -F response_format="json"

To hot-swap the model (path must be readable, e.g. under /srv/ai):

  curl http://127.0.0.1:8081/load \
    -H "Content-Type: multipart/form-data" \
    -F model="/srv/ai/ggml-small.en.bin"

There is no built-in API key. Do not bind HOST to a public address
without a reverse proxy. --convert shells out to ffmpeg.

%package examples
Summary:	CLI tools and helpers for %{name}
Group:		Sciences/Other
Requires:	%{name}%{?_isa} = %{EVRD}
Recommends:	curl

%description examples
CLI tools (whisper-cli, whisper-bench, whisper-quantize,
whisper-vad-speech-segments, parakeet-cli, parakeet-quantize),
model download scripts, and the jfk sample clip.

Download a model (needs curl/wget; writes into the second argument,
or the current directory if the script lives under */bin):

  %{_datarootdir}/%{name}/models/download-ggml-model.sh base.en /var/tmp

  whisper-cli -m /var/tmp/ggml-base.en.bin \
    -f %{_datarootdir}/%{name}/samples/jfk.wav
%endif

%prep
%autosetup -p1 -n whisper.cpp-%{version}

# Guarantee we cannot compile the vendored copy (0.18.1). Backends come
# from the system ggml package.
rm -rf ggml
find . -name '.gitignore' -delete 2>/dev/null || true

%if %{with examples}
%install -a
mkdir -p %{buildroot}%{_unitdir} %{buildroot}%{_sysconfdir}/sysconfig
cat >%{buildroot}%{_unitdir}/whisper.service <<'UNIT'
[Unit]
Description=Speech-to-text HTTP server (whisper.cpp)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# Wrapper sources the sysconfig (multiline MODEL_CANDIDATES) and
# picks the best installed model. Do not use EnvironmentFile —
# systemd cannot parse a multiline list there.
ExecStart=%{_libexecdir}/%{name}/whisper-server-start
KillMode=process
Restart=on-failure
RestartSec=5s

# Unprivileged, no extra caps. Model file must be readable by this user
# (e.g. mode 0644 under /srv/ai — /home is hidden, see ProtectHome).
DynamicUser=yes
SupplementaryGroups=render video
UMask=0077
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes
ProtectHostname=yes
ProtectClock=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectProc=invisible
RestrictNamespaces=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK
SystemCallArchitectures=native
RemoveIPC=yes

# /usr /boot /etc read-only; /home /root invisible. Private /tmp.
# Models: /srv/ai is visible read-only ("-" = skip if missing).
# Extra trees: drop-in  ReadOnlyPaths=-/other/models
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateUsers=no
ReadOnlyPaths=-/srv/ai
# Mesa/Vulkan shader cache, HIP dumps, ffmpeg --convert scratch
CacheDirectory=whisper-server
Environment=XDG_CACHE_HOME=%{_localstatedir}/cache/whisper-server

# GPU: DRM render node + KFD (ROCm). No MemoryDenyWriteExecute —
# Vulkan/HIP compile executable code.
DevicePolicy=closed
DeviceAllow=/dev/null rw
DeviceAllow=/dev/zero rw
DeviceAllow=/dev/urandom r
DeviceAllow=/dev/random r
DeviceAllow=char-drm rw
DeviceAllow=/dev/dri rw
DeviceAllow=/dev/kfd rw

[Install]
WantedBy=multi-user.target
UNIT

mkdir -p %{buildroot}%{_libexecdir}/%{name}
cat >%{buildroot}%{_libexecdir}/%{name}/whisper-server-start <<'SH'
#!/bin/bash
# Resolve a Whisper ggml model and exec whisper-server.
# Sourced config: /etc/sysconfig/whisper-server
set -u

sysconfig=${WHISPER_SYSCONFIG:-/etc/sysconfig/whisper-server}
# shellcheck source=/dev/null
[ -r "$sysconfig" ] && . "$sysconfig"

log() { printf 'whisper-server: %s\n' "$*" >&2; }

readable() { [ -f "$1" ] && [ -r "$1" ]; }

# First readable path in a whitespace-separated list (globs allowed).
pick_from_candidates() {
	local cand f
	shopt -s nullglob
	for cand in $1; do
		case "$cand" in
		\#*) continue ;;
		esac
		for f in $cand; do
			if readable "$f"; then
				printf '%s\n' "$f"
				return 0
			fi
		done
	done
	return 1
}

# Best → worst name, then variant (full > .en > q8 > q5 > tdrz),
# then directory (admin tree before packaged).
pick_from_order() {
	local name dir fmt path
	local -a names dirs
	read -r -a names <<< "$1"
	read -r -a dirs <<< "$2"
	for name in "${names[@]}"; do
		[ -z "$name" ] && continue
		for fmt in \
			"ggml-${name}.bin" \
			"ggml-${name}.en.bin" \
			"ggml-${name}-q8_0.bin" \
			"ggml-${name}.en-q8_0.bin" \
			"ggml-${name}-q5_0.bin" \
			"ggml-${name}.en-q5_0.bin" \
			"ggml-${name}-q5_1.bin" \
			"ggml-${name}.en-q5_1.bin" \
			"ggml-${name}.en-tdrz.bin"
		do
			for dir in "${dirs[@]}"; do
				[ -z "$dir" ] && continue
				path="${dir%/}/${fmt}"
				if readable "$path"; then
					printf '%s\n' "$path"
					return 0
				fi
			done
		done
	done
	return 1
}

model=
if [ -n "${MODEL:-}" ]; then
	if readable "$MODEL"; then
		model=$MODEL
	else
		log "MODEL=$MODEL is not a readable file"
		exit 1
	fi
elif [ -n "${MODEL_CANDIDATES:-}" ]; then
	if ! model=$(pick_from_candidates "$MODEL_CANDIDATES"); then
		log "none of MODEL_CANDIDATES is readable"
		exit 1
	fi
else
	order=${MODEL_ORDER:-"large-v3 large-v3-turbo large-v2 large-v1 medium small base tiny"}
	dirs=${MODEL_DIRS:-"/srv/ai /usr/share/whisper-cpp/models"}
	if ! model=$(pick_from_order "$order" "$dirs"); then
		log "no ggml-*.bin found under: $dirs"
		log "install a whisper-cpp-model-* package, drop a model in /srv/ai, or set MODEL="
		exit 1
	fi
fi

log "using $model"
# WHISPER_PRINT_MODEL=1 → print the path and exit (used by tests / debugging).
if [ -n "${WHISPER_PRINT_MODEL:-}" ]; then
	printf '%s\n' "$model"
	exit 0
fi

cmd=(/usr/bin/whisper-server --model "$model")
[ -n "${HOST:-}" ] && cmd+=(--host "$HOST")
[ -n "${PORT:-}" ] && cmd+=(--port "$PORT")
if [ -n "${WHISPER_OPTIONS:-}" ]; then
	# Intentional split: WHISPER_OPTIONS is a flag string.
	# shellcheck disable=SC2206
	extra=( $WHISPER_OPTIONS )
	cmd+=("${extra[@]}")
fi

exec "${cmd[@]}"
SH
chmod 0755 %{buildroot}%{_libexecdir}/%{name}/whisper-server-start

cat >%{buildroot}%{_sysconfdir}/sysconfig/whisper-server <<'CFG'
# ggml Whisper model (https://huggingface.co/ggerganov/whisper.cpp).
# The unit hides /home and /root (ProtectHome=yes). Packaged models
# under /usr/share/whisper-cpp/models are visible (ProtectSystem=strict
# leaves /usr readable). /srv/ai is extra (ReadOnlyPaths=-/srv/ai; "-"
# means the unit still starts if that directory is absent). Files must
# be readable by the service (e.g. chmod 0644). Extra trees: drop-in
#   ReadOnlyPaths=-/other/models
#
# Resolution, first match wins:
#   1. MODEL=          exact path (error if missing)
#   2. MODEL_CANDIDATES  whitespace-separated paths/globs
#   3. MODEL_ORDER × variants × MODEL_DIRS
# Variants per name, in order: full, .en, q8_0, .en-q8_0, q5_0,
# .en-q5_0, q5_1, .en-q5_1, .en-tdrz. Directories: first listed wins
# for the same file name (so /srv/ai overrides a packaged copy).
#MODEL=/srv/ai/ggml-base.en.bin
#MODEL_CANDIDATES="/srv/ai/ggml-small.en.bin /usr/share/whisper-cpp/models/ggml-tiny.en.bin"
MODEL_ORDER="large-v3 large-v3-turbo large-v2 large-v1 medium small base tiny"
MODEL_DIRS="/srv/ai /usr/share/whisper-cpp/models"
# whisper-server has no --api-key. Anyone who can reach HOST:PORT can
# transcribe and /load a model path the service can read. Keep HOST on
# loopback or put a reverse proxy with auth in front.
HOST=127.0.0.1
# 8081 so this can run next to llama-server (8080). Upstream default
# for a manual whisper-server is 8080.
PORT=8081
# GPU is on by default (ggml backends: Vulkan, HIP/ROCm, …).
# Disable:              WHISPER_OPTIONS="--no-gpu"
# Device index:         WHISPER_OPTIONS="--device 0"
#   (or env WHISPER_ARG_DEVICE=0). Not llama's --device Vulkan0 —
#   backend plugins are loaded automatically from the ggml package.
# Non-WAV uploads:      WHISPER_OPTIONS="--convert"
#   requires ffmpeg; the server exits at start if ffmpeg is missing.
#   Temp files go to the unit's private /tmp.
# VAD:                  WHISPER_OPTIONS="--vad --vad-model /srv/ai/ggml-silero-v6.2.0.bin"
# Language:             WHISPER_OPTIONS="--language auto"
WHISPER_OPTIONS=
CFG

mkdir -p %{buildroot}%{_datarootdir}/%{name}/models
install -m 0755 models/download-ggml-model.sh models/download-vad-model.sh \
	%{buildroot}%{_datarootdir}/%{name}/models/
install -m 0644 models/README.md \
	%{buildroot}%{_datarootdir}/%{name}/models/
cp -a samples %{buildroot}%{_datarootdir}/%{name}/
# Do not ship dummy for-tests-*.bin models or convert-*.py (torch, etc.).
%endif

%if %{with test}
%if %{with check}
%check
cd _OMV_rpm_build && ctest --output-on-failure || true
%endif
%endif

%files
%license LICENSE
%{_libdir}/libwhisper.so.*
%{_libdir}/libparakeet.so.*

%files devel
%doc README.md
%{_includedir}/whisper.h
%{_includedir}/parakeet.h
%{_libdir}/libwhisper.so
%{_libdir}/libparakeet.so
%{_libdir}/cmake/whisper/
%{_libdir}/cmake/parakeet/
%{_libdir}/pkgconfig/whisper.pc
%{_libdir}/pkgconfig/parakeet.pc

%if %{with test}
%files test
%{_bindir}/test-*
%endif

%if %{with examples}
%files server
%{_bindir}/whisper-server
%{_libexecdir}/%{name}/whisper-server-start
%{_unitdir}/whisper.service
%config(noreplace) %{_sysconfdir}/sysconfig/whisper-server

%files examples
%{_bindir}/whisper-*
%exclude %{_bindir}/whisper-server
%{_bindir}/parakeet-*
%{_datarootdir}/%{name}/
%endif
