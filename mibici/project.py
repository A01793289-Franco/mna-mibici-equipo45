import argparse
from contextlib import nullcontext

from mibici import config as cfg
from mibici import train
from mibici.tracking import log_bundle, project_run


def resolve(value, default, converter=str):
    return default if value == "config" else converter(value)


def boolean(value):
    if value.lower() not in ("true", "false"):
        raise ValueError("Usa true o false")
    return value.lower() == "true"


def training_arguments(args):
    arguments = ["--question", args.question, "--model", args.model]
    arguments += ["--seed", str(resolve(args.seed, cfg.SEED, int))]
    arguments += ["--n-clusters", str(resolve(args.n_clusters, cfg.N_CLUSTERS, int))]
    if resolve(args.tune, cfg.PROJECT_TUNE, boolean):
        arguments.append("--tune")
    if resolve(args.final_test, cfg.PROJECT_FINAL_TEST, boolean):
        arguments.append("--final-test")
    register_default = cfg.PROJECT_REGISTER and args.model == "all"
    if not resolve(args.register, register_default, boolean):
        arguments.append("--no-register")
    for key in ("learning_rate", "max_iter", "max_leaf_nodes", "l2_regularization", "c"):
        value = getattr(args, key)
        if value != "config":
            arguments += ["--" + key.replace("_", "-"), value]
    arguments += ["--figures-dir", str(cfg.FIGURES_DIR / "experimentos")]
    return arguments


def ingest_project(refresh=False):
    import mlflow
    from mibici.dataset import ingest
    from mibici.features import build_features

    train.configure_mlflow()
    with project_run():
        scope = nullcontext() if mlflow.active_run() else mlflow.start_run(run_name="ingest")
        with scope:
            mlflow.set_tags({"equipo": cfg.TEAM, "stage_of_work": "ingest"})
            source = ingest(refresh=refresh)
            features = build_features()
            context = train.run_context()
            mlflow.set_tags(context)
            params = {
                "start": cfg.START_DATE.isoformat(),
                "end_exclusive": cfg.END_DATE_EXCLUSIVE.isoformat(),
                "refresh": refresh,
                "data_version": source["data_version"],
                "feature_version": features["feature_version"],
            }
            mlflow.log_params({"resolved_" + key: str(value) for key, value in params.items()})
            mlflow.log_metric("clean_trips", source["summary"]["clean_trips"])
            log_bundle(context, params)


def parser():
    result = argparse.ArgumentParser(
        description="Entradas reproducibles del MLflow Project MiBici"
    )
    commands = result.add_subparsers(dest="command", required=True)
    ingestion = commands.add_parser("ingest", help="Descarga, limpia y construye variables")
    ingestion.add_argument(
        "--refresh", default="false", help="true acepta nuevas fuentes y hashes"
    )
    training = commands.add_parser("train", help="Entrena una pregunta o el protocolo completo")
    training.add_argument("--question", default="all", help="p1, p2, p3 o all")
    training.add_argument("--model", default="all", help="Modelo compatible con la pregunta")
    for name, description in (
        ("seed", "Semilla"),
        ("learning-rate", "Tasa de aprendizaje HGB"),
        ("max-iter", "Iteraciones HGB o regresión logística"),
        ("max-leaf-nodes", "Hojas por árbol HGB"),
        ("l2-regularization", "Regularización HGB"),
        ("c", "Inverso de regularización logística"),
        ("n-clusters", "Número de grupos P3"),
        ("tune", "Búsqueda: true/false"),
        ("final-test", "Evaluación final de septiembre: true/false"),
        ("register", "Promoción a champion: true/false"),
    ):
        training.add_argument(
            "--" + name, default="config", help=description + "; config usa config.py"
        )
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        if args.command == "ingest":
            ingest_project(boolean(args.refresh))
        else:
            arguments = training_arguments(args)
            train.main(arguments)
    except ValueError as error:
        cli.error(str(error))


if __name__ == "__main__":
    main()
