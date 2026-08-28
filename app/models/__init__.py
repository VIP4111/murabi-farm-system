from app.models.role import Role, Permission, role_permissions
from app.models.user import User
from app.models.barn import Barn, BarnFeedingSchedule
from app.models.animal import Animal
from app.models.animal_options import SpeciesType, Breed, AnimalColor
from app.models.settings import ServiceToggle
from app.models.audit import AuditLog
from app.models.rate_limit import RateLimitHit
from app.models.telegram_update import ProcessedTelegramUpdate
from app.models.pharmacy import Pharmacy, PharmacyBatch
from app.models.pharmacy_dose_rule import PharmacyDoseRule
from app.models.usage_route import UsageRoute
from app.models.report_type import ReportType
from app.models.drug_catalog import DrugCatalogEntry
from app.models.vaccination_schedule import VaccinationSchedule
from app.models.doctor import Doctor
from app.models.health import VetVisit, Disease, Vaccination, DiseaseType, Symptom, DiseaseSymptomLink, EmergencySymptom
from app.models.finance import Finance
from app.models.payroll import Payroll, PayrollDeduction, WorkerTravelPeriod
from app.models.repro import (
    Mating, Pregnancy, TwinEstrusProgram, TwinEstrusAttempt,
    ReproDevice, HormoneInjection, SonarResult,
)
from app.models.cycle import ProductionWorkflow, CycleEvent
from app.models.report import Report
from app.models.task import Task, DailyTaskTemplate
from app.models.feed import Feed, FeedRation, FeedRationItem, FeedBarnPlan, FeedMovement
from app.models.farm_settings import FarmSettings
from app.models.animal_log import AnimalWeight, AnimalNote
from app.models.birth_record import BirthRecord
from app.models.milk_record import MilkRecord
from app.models.ostrich import Incubator, OstrichEgg
from app.models.assistant import AssistantMessage
from app.models.climate import WeatherReading
from app.models.protocol import TreatmentProtocol, TreatmentProtocolStep, ProtocolApplication
from app.models.animal_batch import AnimalBatch
from app.models.warehouse import Warehouse, FeedWarehouseStock, PharmacyWarehouseStock
from app.models.equipment import Equipment, EquipmentMovement
from app.models.checklist import ChecklistItem, ChecklistCompletion
from app.models.sales_lot import SalesLot, SalesLotItem
from app.models.asset import Asset, AssetMaintenanceLog, UtilityReading
from app.models.inventory_count import InventoryCount
from app.models.farm_note import FarmNote, FarmNoteEmbedding

__all__ = [
    "Role", "Permission", "role_permissions",
    "User", "Barn", "BarnFeedingSchedule", "Animal", "SpeciesType", "Breed", "AnimalColor",
    "ServiceToggle", "AuditLog", "RateLimitHit",
    "Pharmacy", "PharmacyBatch", "PharmacyDoseRule", "UsageRoute", "DrugCatalogEntry", "VaccinationSchedule", "Doctor", "ReportType",
    "VetVisit", "Disease", "Vaccination", "DiseaseType", "Symptom", "DiseaseSymptomLink", "EmergencySymptom",
    "Finance",
    "Mating", "Pregnancy", "TwinEstrusProgram", "TwinEstrusAttempt",
    "ReproDevice", "HormoneInjection", "SonarResult",
    "ProductionWorkflow", "CycleEvent",
    "Report", "Task", "DailyTaskTemplate",
    "Feed", "FeedRation", "FeedRationItem", "FeedBarnPlan", "FeedMovement",
    "FarmSettings",
    "AnimalWeight", "AnimalNote",
    "BirthRecord",
    "MilkRecord",
    "Incubator", "OstrichEgg",
    "AssistantMessage",
    "WeatherReading",
    "TreatmentProtocol", "TreatmentProtocolStep", "ProtocolApplication",
    "AnimalBatch",
    "Warehouse", "FeedWarehouseStock", "PharmacyWarehouseStock",
    "Equipment", "EquipmentMovement",
    "ProcessedTelegramUpdate",
    "ChecklistItem", "ChecklistCompletion",
    "Asset", "AssetMaintenanceLog", "UtilityReading",
    "SalesLot", "SalesLotItem",
    "InventoryCount",
    "FarmNote", "FarmNoteEmbedding",
]
