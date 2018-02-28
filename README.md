# Meal Delivery Routing Problem Test Instances

This repository contains problem files used to test models for solving the Meal Delivery Routing Problem and a solution evaluator. The sample instances have been provided by [Grubhub](https://www.grubhub.com) and Georgia Tech's [H. Milton Stewart School of Industrial & Systems Engineering](https://www.isye.gatech.edu/) to advance research on the subject.

The `public_instances` folder contains 240 instances using anonymized data from meal delivery operations at Grubhub. These were derived from a set of 10 seed instances through the following procedure.

* Reducing their size. This defines three subsets of instances: 
	- `o100`: no size reduction
	- `o50`: 50% reduction in number of orders and courier hours, sampling the order set directly.
	- `r50`: 50% reduction in number of orders and courier hours, sampling the restaurant set and keeping all orders from selected restaurants.
* Changing the courier schedule. This defines two subsets:
	- `s1`: schedule based on historical courier shifts.
	- `s2`: schedule with "optimized shifts" (subject to having about the same, and never more, courier hours than the historical counterpart) 
* Increasing the travel speed. This defines two subsets:
	- `t100`: original travel times
	- `t75`: travel times are multiplied by 0.75
* Increasing the preparation times of all orders. This defines two subsets:
	- `p100`: original preparation times
	- `p125`: preparation times are multiplied by 1.25

Each instance is then labeled by concatenating the labels of the sets to which it belongs. For example: `1o50s2t100p125` is the instance derived from seed 1, by reducing its size by 50% on the order set, using an optimized courier schedule, original travel speed, and longer preparation times; and seed 1 is represented as `1o100s1t100p100`.

The folder `MDRP_code` contains the solution evaluator script. [Meal Delivery Routing: The Grubhub Instances](MDRPInstances.pdf?raw=true) provides a complete description of the Meal Delivery Routing Problem and the test instance set.
