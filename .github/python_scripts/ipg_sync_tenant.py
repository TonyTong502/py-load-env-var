import os

def main():
    my_variable_value = os.getenv("MY_VARIABLE")
    if my_variable_value:
        print(f"The value of MY_VARIABLE is: {my_variable_value}")
    else:
        print("MY_VARIABLE not found.")

    my_env_value = os.getenv("MY_ENV")
    if my_env_value:
        print(f"The value of MY_ENV is: {my_env_value}")
    else:
        print("MY_ENV not found.")

if __name__ == "__main__":
    main()
