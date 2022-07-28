FROM jupyter/base-notebook

WORKDIR /nb-docker

COPY custom ./custom
COPY jupyter_notebook_config.py jupyter_notebook_config.py

USER ${NB_UID}
COPY --chown=jovyan:users pyhamilton pyhamilton
RUN cd pyhamilton && pip install -e '.[simulation]'

COPY --chown=jovyan:users template.ipynb ./notebooks/notebook.ipynb
# --chmod=0755

EXPOSE 8888
EXPOSE 2121
EXPOSE 1337

ENV RICK yes

ENV JUPYTER_CONFIG_DIR = .

#ENTRYPOINT ["jupyter", "notebook", "--port=8888"]
ENTRYPOINT ["jupyter", "notebook", "--port=8888", "--config=jupyter_notebook_config.py", "--ip=0.0.0.0", "notebooks"]
