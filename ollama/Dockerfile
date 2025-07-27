FROM ollama/ollama:0.9.6@sha256:f478761c18fea69b1624e095bce0f8aab06825d09ccabcd0f88828db0df185ce

RUN apt-get update -qq \
    && apt-get install -qq --assume-yes \
      wait-for-it \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    ;

# Copy the startup script
COPY --chmod=555 start.sh /usr/local/bin/start.sh

ENTRYPOINT ["/usr/local/bin/start.sh"]

CMD ["gemma3:1b"]
