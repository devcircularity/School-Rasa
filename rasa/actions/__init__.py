"""
Rasa Custom Actions Package
Organized by functionality: students, academic management, fees, guardians, notifications, and Ollama-powered actions
"""

# ============================================
# STUDENT ACTIONS
# ============================================
from actions.student_actions import (
    ActionCreateStudent,
    ActionListStudents,
    ActionListStudentsByClass,
    ActionSearchStudent,
    ActionListUnassignedStudents,
    ActionAssignStudentToClass,
    ActionProvideAdmissionNumber,
    ActionAutoGenerateAdmission,
    ActionReenrollStudent,
    ActionShowUnassignedStudents,
    ActionGetStudentDetails,
    ValidateStudentCreationForm,
)

# ============================================
# ACADEMIC/CLASS MANAGEMENT ACTIONS
# ============================================
from actions.academic_actions import (
    ActionCreateAcademicYear,
    ActionCreateAcademicTerm,
    ActionCheckAcademicSetup,
    ActionGetCurrentAcademicYear,
    ActionGetCurrentTerm,
    ActionActivateAcademicYear,
    ActionDeactivateAcademicYear,
    ActionActivateTerm,
    ActionListAcademicTerms,
    ActionPromoteStudents,
    ActionCreateClass,
    ActionListClasses,
    ActionListEmptyClasses,
    ActionDeleteClass,
    ActionHelp,
    ActionCompleteTerm,
)

# ============================================
# FEE ACTIONS
# ============================================
from actions.fee_actions import (
    ActionCreateFeeStructure,
    ActionListFeeStructures,
    ActionGenerateInvoices,
    ActionGetInvoice,
    ActionAddFeeItem,
    ActionViewFeeStructureDetails,
    ActionDeleteFeeItems,
    ActionDeleteSpecificFeeItem,
    ActionPublishFeeStructure,
    ActionSetDefaultFeeStructure,
    ActionSetStructureAsDefault,
    ActionIssueInvoices,
    ActionListInvoices,
    ActionListInvoicesByClass,
    ActionListUnpaidInvoices,
    ActionListStudentsWithBalances,
    ActionCancelInvoice,
    ActionRecordPayment,
    ActionSendPaymentNotification,
    ActionResetSlots,
    ActionNotifyParentsWithBalances,
    ActionBroadcastMessageToAllParents,
)

# ============================================
# GUARDIAN ACTIONS
# ============================================
from actions.guardian_actions import (
    ActionAddGuardian,
    ActionGetGuardians,
    ActionListStudentsWithoutGuardians,
    ActionSetPrimaryGuardian,
    ActionUpdateGuardian,
    ActionListAllGuardians
)

# ============================================
# NOTIFICATION ACTIONS
# ============================================
from actions.notification_actions import (
    ActionNotifyPendingInvoices,
    ActionSendGuardianMessage,
)

# ============================================
# SCHOOL INFO ACTIONS
# ============================================
from actions.school_info_actions import ActionGetSchoolInfo

# ============================================
# FORM HELPERS
# ============================================
from actions.form_helpers import (
    ActionResumeStudentForm,
    ActionHandleFormInterruption,
)

# ============================================
# FORM VALIDATORS
# ============================================
from actions.form_validators import (
    ActionValidateStudentCreationPrerequisites,
)



# ============================================
# EXPORT ALL ACTIONS
# ============================================
__all__ = [
    # ========== Student actions ==========
    "ActionCreateStudent",
    "ActionListStudents",
    "ActionListStudentsByClass",
    "ActionSearchStudent",
    "ActionListUnassignedStudents",
    "ActionAssignStudentToClass",
    "ActionProvideAdmissionNumber",
    "ActionAutoGenerateAdmission",
    "ActionReenrollStudent",
    "ActionShowUnassignedStudents",
    "ActionGetStudentDetails",
    "ValidateStudentCreationForm",
    
    # ========== Academic/Class management actions ==========
    "ActionCreateAcademicYear",
    "ActionCreateAcademicTerm",
    "ActionCheckAcademicSetup",
    "ActionGetCurrentAcademicYear",
    "ActionGetCurrentTerm",
    "ActionActivateAcademicYear",
    "ActionDeactivateAcademicYear",
    "ActionActivateTerm",
    "ActionListAcademicTerms",
    "ActionPromoteStudents",
    "ActionCreateClass",
    "ActionListClasses",
    "ActionListEmptyClasses",
    "ActionDeleteClass",
    "ActionHelp",
    "ActionCompleteTerm",
    
    # ========== Fee actions ==========
    "ActionCreateFeeStructure",
    "ActionListFeeStructures",
    "ActionGenerateInvoices",
    "ActionGetInvoice",
    "ActionAddFeeItem",
    "ActionViewFeeStructureDetails",
    "ActionDeleteFeeItems",
    "ActionDeleteSpecificFeeItem",
    "ActionPublishFeeStructure",
    "ActionSetDefaultFeeStructure",
    "ActionSetStructureAsDefault",
    "ActionIssueInvoices",
    "ActionListInvoices",
    "ActionListInvoicesByClass",
    "ActionListUnpaidInvoices",
    "ActionListStudentsWithBalances",
    "ActionCancelInvoice",
    "ActionRecordPayment",
    "ActionSendPaymentNotification",
    "ActionResetSlots",
    "ActionNotifyParentsWithBalances",
    "ActionBroadcastMessageToAllParents",
    
    # ========== Guardian actions ==========
    "ActionAddGuardian",
    "ActionGetGuardians",
    "ActionListStudentsWithoutGuardians",
    "ActionSetPrimaryGuardian",
    "ActionUpdateGuardian",
    "ActionListAllGuardians",
    
    # ========== Notification actions ==========
    "ActionNotifyPendingInvoices",
    "ActionSendGuardianMessage",

    # ========== School info actions ==========
    "ActionGetSchoolInfo",

    # ========== Form helpers ==========
    "ActionResumeStudentForm",
    "ActionHandleFormInterruption",

    # ========== Form validators ==========
    "ActionValidateStudentCreationPrerequisites",

    "ActionOllamaBridge",
]
