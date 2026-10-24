from enum import Enum


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class YesNo(str, Enum):
    yes = "yes"
    no = "no"


class PassType(str, Enum):
    work_permit = "work_permit"
    s_pass = "s_pass"
    employment_pass = "employment_pass"
    student_pass = "student_pass"
    other = "other"


class BookStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"