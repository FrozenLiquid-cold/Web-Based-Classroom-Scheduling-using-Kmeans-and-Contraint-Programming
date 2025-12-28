export const seedData = {
	college: [
		{ id: 'college-cas', code: 'CAS', description: 'College of Arts and Sciences' },
		{ id: 'college-cet', code: 'CET', description: 'College of Engineering and Technology' },
	],
	course: [
		{ id: 'course-bsit', collegeId: 'college-cet', code: 'BSIT', description: 'BS Information Technology' },
		{ id: 'course-bsed', collegeId: 'college-cas', code: 'BSED', description: 'BS Education' },
	],
	instructor: [
		{ id: 'inst-1', firstName: 'Juan', lastName: 'Dela Cruz' },
		{ id: 'inst-2', firstName: 'Maria', lastName: 'Santos' },
	],
	day: [
		{ id: 'day-mon', label: 'M' },
		{ id: 'day-tue', label: 'T' },
		{ id: 'day-wed', label: 'W' },
		{ id: 'day-thu', label: 'TH' },
		{ id: 'day-fri', label: 'F' },
	],
	subject: [
		{ id: 'sub-cc101', code: 'CC101', description: 'Intro to Computing', type: 'LEC', unit: 3 },
		{ id: 'sub-cc102', code: 'CC102', description: 'Programming 1', type: 'LAB', unit: 2 },
	],
	room: [
		{ id: 'room-101', name: 'Room 101', type: 'LEC' },
		{ id: 'room-lab1', name: 'Lab 1', type: 'LAB' },
	],
}

