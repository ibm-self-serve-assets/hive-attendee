# Order Fulfillment and Priotitizing Parts Manufacturing

## Overview & Goal

At the end of Level 3, you may have noticed a new UI element in the top-right of your Hive Dashboard: the list of orders placed for new robots now appears as the **Robot assembly queue**.  In this case, there are 3 orders in the queue: 2 x **G**atherer robots followed by an **E**ngineer robot.  

This introduces a new problem. How do we prioritize manufacturing parts based on existing robot orders in the queue.  The robot assembly stations know their required parts and need to communicate this through the event-driven architecture.  So we need to avoid adding a hard-coded REST call to "place orders for parts".  

<img src="screenshots/robot_assembly_queue.png"/>




