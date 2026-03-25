FROM cloudblueconnect/connect-extension-runner:37.0

COPY pyproject.toml /install_temp/
WORKDIR /install_temp
RUN poetry install --no-root
