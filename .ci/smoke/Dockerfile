# Pipeline smoke test. Never published, never pulled by anyone.
#
# Everything about the real pipeline that cannot be proven by a script runs through
# .github/actions/build-image: the local composite action itself, its input validation, the tag
# and build-arg composition, the publish gate that skips login and cache export, and buildx with
# QEMU producing a multi-arch index. Before this file existed none of it had ever executed, and a
# mistake in the action only surfaced the first time a real image was pushed.
#
# So the workflow's `smoke` job builds this file with publish=false on every pull request.
# It takes seconds, touches nothing, and fails the PR if the action is broken.
#
# Two constraints keep it cheap and correct:
#   - no COPY: .dockerignore excludes .ci, so the build context does not contain this directory.
#     The file itself is fine — buildx reads the Dockerfile outside the context.
#   - a pinned upstream digest-free tag is fine here because nothing is shipped from it.
FROM alpine:3.20

# Declared so the action's overrides land on real ARGs instead of "unused build arg" noise.
ARG VERSION=ci/smoke
ARG GIT_SHA=unknown
ARG BUILD_CREATED=1970-01-01T00:00:00Z
ARG IMAGE_DESCRIPTION=Pipeline smoke test; never published
LABEL org.opencontainers.image.title="coder-images-ci-smoke" \
      org.opencontainers.image.description="${IMAGE_DESCRIPTION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_CREATED}"

# Proves a layer really builds and that a build arg reaches the build, not just the metadata.
RUN test -n "${VERSION}" && echo "smoke build for ${VERSION}" > /smoke-marker
