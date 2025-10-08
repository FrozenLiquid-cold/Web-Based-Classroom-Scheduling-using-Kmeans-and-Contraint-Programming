from scheduling.utils import clear_screen
from scheduling.scheduler import create_schedule, Debugger  # use the updated version with debugger
from globals import Globals






def ViewSched():
        clear_screen()
        print("=== CLASS-KCP MENU ===")
        if Globals.schedules == 0 :
            print("\n     No Schedules\n")
            input("press enter to continue...")
            show_menu()




def CreateSched():
      
        print("=== CLASS-KCP MENU ===")
        print("\nSelect a College")
        print("\n1. College of Computing Studies")
        choice = input("\nSelect an option: ").strip()
        if choice == '1':
            clear_screen()
            SelectCourse()
        else:
            clear_screen()
            print("Please SELECT a number from the choices: ")
            input("Press Enter to continue..")
            CreateSched()

def SelectCourse():
        print("=== CLASS-KCP MENU ===")
        print("\nSelect a course: ")
        print("1. BSIS ")
        print("2. BSIT ")
        print("3. BSCS ")
        choice = input("\nSelect course: ").strip()
        if choice == '1':
            print("\nBSIS is not available yet...")
            input("\nPress Enter to continue..")
            clear_screen()
            SelectCourse()
        elif choice == '2':
            print("\nBSIT is not available yet...")
            input("\nPress Enter to continue..")
            clear_screen()
            SelectCourse()
        elif choice == '3':
            clear_screen()
            SelectYearLvl()
        else:
            print("Please SELECT a number from the choices: ")
            input("Press Enter to continue..")
            clear_screen()
            SelectCourse()

def SelectYearLvl():
        
        print("=== CLASS-KCP MENU ===")
        print("\nSelect Year Level: ")
        print("1. 1 ")
        print("2. 2 ")
        print("3. 3")
        print("4. 4")
        choice = input("\nSelect an option: ").strip()
        if choice == '1':
             Globals.yearLvl = 1
             clear_screen()
             SelectBlock()
        elif choice =='2':
             Globals.yearLvl = 2
             clear_screen()
             SelectBlock()
        elif choice =='3':
             Globals.yearLvl = 3
             clear_screen()
             SelectBlock()
        elif choice =='4':
             Globals.yearLvl = 4
             clear_screen()
             SelectBlock()
        else:
             print("\nnot in the options!")
             input("\nPress Enter to continue...")
             clear_screen()
             SelectYearLvl()

def SelectBlock():
        print("=== CLASS-KCP MENU ===")
        print("\nSelect an option: ")
        print("1. A ")
        print("2. B ")
        print("3. C")     
        choice = input("Select Block: ").strip()
        if choice == '1':
             Globals.block = 'A'
             clear_screen()
             SelectSem()
        elif choice == '2':
             Globals.block = 'B:'
             clear_screen()
             SelectSem()
        elif choice == '3':
             Globals.block = 'C:'
             clear_screen()
             SelectSem()
        else:
            print("\nnot in the options!")
            input("\nPress Enter to continue...")
            clear_screen()
            SelectBlock()

def SelectSem():
    print("=== CLASS-KCP MENU ===")
    print("\nSelect an option: ")
    print("1. First Semester ")
    print("2. Second Semester ")
    choice = input("\nSelect semester: ").strip()

    if choice == '1':
        Globals.semester = 1
    elif choice == '2':
        Globals.semester = 2
    else:
        print("\nnot in the options!")
        input("")
        clear_screen()
        SelectSem()
        return

    clear_screen()
    print("Generating schedule...")
    # initialize debugger
    debug = Debugger(enable_console=True, filename="schedule_debug.log")
    schedules = create_schedule()

    if not schedules:
        print("\nNo valid schedule found.")
    else:
        print("\n=== Generated Schedule ===")
        for s in schedules:
            print(f"{s['Code']} | {s['Title']} | {s['Time']} | {s['Room']} | {s['Instructor']}")
        print("\nSchedule also saved to: schedule_debug.log")

    input("\nPress Enter to continue...")



def show_menu():

    clear_screen()
    print("=== CLASS-KCP MENU ===")
    print("1. View Schedules")
    print("2. Create Schedule")
    print("3. Exit")



def main():
    # Print the title
    print("=== CLASS-KCP ===\n")
    input("Press Enter to continue...")
    
    while True:
        clear_screen()
        show_menu()
        
        choice = input("\nSelect an option: ").strip()
        
        if choice == '1':
            print("\nYou selected View Schedules")
            input("\nPress Enter to continue...")
            clear_screen()
            ViewSched()
            
        elif choice == '2':
            print("\nYou selected Create Schedule")
            input("\nPress Enter to continue...")
            clear_screen()
            CreateSched()
        elif choice == '3':
            print("\nExiting CLASS-KCP. Goodbye!")
            break
        else:
            print("\nInvalid choice. Try again.")
        
        input("\nPress Enter to return to the menu...")

if __name__ == "__main__":
    main()



# === CLASS-KCP MENU ===
# 1. View Schedules
# 2. Create Schedule
# 3. Exit

# Select an option: 
