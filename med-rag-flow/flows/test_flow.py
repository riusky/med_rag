from prefect import flow


@flow
def my_flow(str: str):
    print(f"Hello, Prefect! {str}")


if __name__ == "__main__":
    my_flow.serve(name="my-first-deployment")