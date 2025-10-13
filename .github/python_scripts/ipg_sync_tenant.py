import os

def main():
    my_variable_value = os.getenv("MY_VARIABLE")
    if my_variable_value:
        print(f"The value of MY_VARIABLE is: {my_variable_value}")
    else:
        print("MY_VARIABLE not found.")

    my_sec_value = os.getenv("MY_SECRET")
    if my_sec_value:
        print(f"The value of MY_SECRET is: {my_sec_value}")
    else:
        print("MY_SECRET not found.")

if __name__ == "__main__":
    main()
